from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from layer_api.schemas import ApiError


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ApiError(422, "validation_error", "Password must be at most 72 bytes")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: str, secret: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode({"sub": user_id, "exp": expires}, secret, algorithm="HS256")


def read_token(token: str, secret: str) -> str | None:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        subject = payload.get("sub")
        return subject if isinstance(subject, str) else None
    except jwt.PyJWTError:
        return None

