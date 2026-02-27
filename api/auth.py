import os
import jwt
from jwt import PyJWTError
from fastapi import Header, HTTPException
from .supabase_client import get_supabase

def require_admin_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")

    token = authorization.split(" ", 1)[1].strip()

    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET is not set")

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    sb = get_supabase()
    rows = (
        sb.table("profiles")
        .select("role")
        .eq("user_id", user_id)   # ✅ matches your schema
        .limit(1)
        .execute()
        .data
    ) or []

    role = rows[0].get("role") if rows else None
    if role is None:
        raise HTTPException(status_code=403, detail="Account not approved yet (no profile)")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Account not approved yet")
    return user_id