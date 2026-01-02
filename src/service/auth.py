import time
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from fastapi import Request, Response, Depends, FastAPI, HTTPException, status
from core import settings
from typing import Any

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def jwt_secret() -> str:
    return settings.JWT_SECRET.get_secret_value()  # type: ignore[attr-defined]


def create_access_token(*, sub: str, roles: list[str]) -> str:
    """ 生成 JWT """
    now = int(time.time())
    # sub: 用户表示
    # iat: issued at, 签发时间
    # exp: expiration time, 过期时间
    # roles: 自定义私有字段, 用户角色列表[admin, editor, viewer]
    payload = {"sub": sub, "roles": roles, "iat": now, "exp": now + settings.JWT_EXPIRES_SECONDS}
    return jwt.encode(payload, jwt_secret(), algorithm=settings.JWT_ALG)


def get_current_user(request: Request) -> dict[str, Any]:
    """ 根据 JWT获取到用户id以及roles列表"""
    token = request.cookies.get(settings.JWT_COOKIE_NAME)

    # 请求cookie没有JWT, 鉴权失败
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        # 用服务端秘钥解码JWT
        payload = jwt.decode(token, jwt_secret(), algorithms=[settings.JWT_ALG])
    except PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    sub = payload.get("sub")
    roles = payload.get("roles", [])
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return {"user_id": sub, "roles": roles}


def require_roles(*allowed: str):
    """ 用于 endpoint, 检查 roles和allowed是否有交集"""
    def _dep(user: dict[str, Any] = Depends(get_current_user)):
        if not set(user.get("roles", [])).intersection(allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return _dep