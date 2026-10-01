from fastapi import Request
from clerk_backend_api import AuthenticateRequestOptions, Clerk, authenticate_request
from clerk_backend_api.models.emailaddress import VerificationStatus

from layer_api.config import Settings
from layer_api.schemas import ApiError


def verify_session(request: Request, settings: Settings) -> str:
    state = authenticate_request(
        request,
        AuthenticateRequestOptions(
            secret_key=settings.clerk_secret_key,
            jwt_key=settings.clerk_jwt_key.replace("\\n", "\n").strip() or None,
            authorized_parties=[settings.frontend_url.rstrip("/")],
            accepts_token=["session_token"],
        ),
    )
    clerk_user_id = state.payload.get("sub") if state.is_signed_in and state.payload else None
    if not isinstance(clerk_user_id, str) or not clerk_user_id:
        raise ApiError(401, "unauthorized", "Please sign in")
    return clerk_user_id


async def clerk_profile(clerk_user_id: str, settings: Settings) -> tuple[str, str]:
    try:
        clerk_user = await Clerk(bearer_auth=settings.clerk_secret_key).users.get_async(user_id=clerk_user_id)
    except Exception as exc:
        raise ApiError(503, "server_error", "Could not load Clerk user") from exc
    primary = next((item for item in clerk_user.email_addresses if item.id == clerk_user.primary_email_address_id), None)
    if primary is None or primary.verification is None or primary.verification.status != VerificationStatus.VERIFIED:
        raise ApiError(403, "forbidden", "Verify your email address in Clerk first")
    email = primary.email_address.lower()
    name = " ".join(part for part in (clerk_user.first_name, clerk_user.last_name) if part).strip()
    return (name or email.split("@", 1)[0])[:100], email
