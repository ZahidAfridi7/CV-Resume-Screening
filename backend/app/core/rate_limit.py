"""Rate limiting for API routes. Used by SlowAPI; key by IP or by user when authenticated."""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import decode_access_token_payload


def get_user_or_ip_key(request):
    """Rate limit by user id when Bearer token is valid, otherwise by IP."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        payload = decode_access_token_payload(auth[7:].strip())
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_remote_address)
