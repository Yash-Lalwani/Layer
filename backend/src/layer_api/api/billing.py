import json
import logging
from datetime import date, datetime, timezone
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Request
from sqlalchemy import case, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.auth.dependencies import get_current_user
from layer_api.config import Settings
from layer_api.db import User, get_session
from layer_api.schemas import ApiError


router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)


def today() -> date:
    return datetime.now(timezone.utc).date()


def daily_limit(user: User, settings: Settings) -> int:
    return settings.pro_questions_per_day if user.plan == "pro" else settings.free_questions_per_day


def questions_left(user: User, settings: Settings) -> int:
    if user.is_guest:
        return max(0, settings.demo_questions_per_guest - user.questions_used)
    used = user.questions_today if user.questions_date == today() else 0
    return max(0, daily_limit(user, settings) - used)


async def use_question(db: AsyncSession, user: User, settings: Settings) -> int:
    """Count one question against the guest total or the plan's daily limit, in a single atomic update."""
    if user.is_guest:
        limit = settings.demo_questions_per_guest
        used = await db.scalar(update(User).where(User.id == user.id, User.questions_used < limit)
                               .values(questions_used=User.questions_used + 1).returning(User.questions_used))
        if used is None:
            raise ApiError(429, "demo_limit_reached", "The demo's 7 questions are used. Sign up to keep exploring.")
    else:
        limit, day = daily_limit(user, settings), today()
        new_day = or_(User.questions_date.is_(None), User.questions_date != day)
        used = await db.scalar(update(User).where(User.id == user.id, or_(new_day, User.questions_today < limit))
                               .values(questions_today=case((new_day, 1), else_=User.questions_today + 1), questions_date=day)
                               .returning(User.questions_today))
        if used is None:
            message = ("You've used today's free questions. Upgrade to Pro for more each day." if user.plan == "free"
                       else "You've used today's questions. They reset at midnight UTC.")
            raise ApiError(429, "daily_limit_reached", message)
    await db.commit()
    return limit - used


def stripe_client(settings: Settings) -> stripe.StripeClient:
    if not settings.stripe_secret_key or not settings.stripe_pro_price_id:
        raise ApiError(503, "server_error", "Billing is not configured")
    return stripe.StripeClient(settings.stripe_secret_key)


def registered(user: User) -> None:
    if user.is_guest:
        raise ApiError(403, "forbidden", "Sign up to manage billing")


@router.post("/checkout")
async def checkout(request: Request, user: Annotated[User, Depends(get_current_user)]):
    registered(user)
    if user.plan == "pro":
        raise ApiError(409, "conflict", "You're already on Pro")
    settings = request.app.state.settings
    params = {"mode": "subscription", "line_items": [{"price": settings.stripe_pro_price_id, "quantity": 1}],
              "client_reference_id": user.id,
              "success_url": f"{settings.frontend_url}/workspace?billing=success",
              "cancel_url": f"{settings.frontend_url}/workspace"}
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    elif user.email:
        params["customer_email"] = user.email
    try:
        session = await stripe_client(settings).v1.checkout.sessions.create_async(params)
    except stripe.StripeError as exc:
        logger.warning("Stripe checkout failed: %s", exc)
        raise ApiError(503, "server_error", "Stripe checkout is unavailable. Please try again.") from None
    return {"url": session.url}


@router.post("/portal")
async def portal(request: Request, user: Annotated[User, Depends(get_current_user)]):
    registered(user)
    if not user.stripe_customer_id:
        raise ApiError(409, "conflict", "There is no billing account yet")
    settings = request.app.state.settings
    try:
        session = await stripe_client(settings).v1.billing_portal.sessions.create_async(
            {"customer": user.stripe_customer_id, "return_url": f"{settings.frontend_url}/workspace"})
    except stripe.StripeError as exc:
        logger.warning("Stripe portal failed: %s", exc)
        raise ApiError(503, "server_error", "Stripe billing is unavailable. Please try again.") from None
    return {"url": session.url}


@router.post("/webhook")
async def webhook(request: Request, db: Annotated[AsyncSession, Depends(get_session)]):
    """Stripe calls this with no Clerk token; the signature proves the event came from Stripe."""
    secret = request.app.state.settings.stripe_webhook_secret
    if not secret:
        raise ApiError(503, "server_error", "Billing is not configured")
    payload = (await request.body()).decode()
    try:
        stripe.WebhookSignature.verify_header(payload, request.headers.get("stripe-signature"), secret)
    except stripe.SignatureVerificationError:
        raise ApiError(400, "validation_error", "Invalid Stripe signature") from None
    event = json.loads(payload)
    data = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        user = await db.get(User, data.get("client_reference_id") or "")
        if user and not user.is_guest:
            user.stripe_customer_id = data["customer"]
            user.plan = "pro"
    elif event["type"] in {"customer.subscription.updated", "customer.subscription.deleted"}:
        user = await db.scalar(select(User).where(User.stripe_customer_id == data["customer"]))
        if user:
            active = event["type"] == "customer.subscription.updated" and data["status"] in {"active", "trialing"}
            user.plan = "pro" if active else "free"
    await db.commit()
    return {"ok": True}
