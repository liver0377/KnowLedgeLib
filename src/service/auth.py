import time
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from fastapi import Request, Response, Depends, FastAPI, HTTPException, status
from core import settings
from typing import Any

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DEMO_ALLOWED_DEPT_KEYS: dict[str, list[str]] = {
    "user-ryan": ["micro_service"],      # admin 看全部
    "user-viewer": ["AI"],   # 只能看 AI 部门
}

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



def get_user_context(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """
    工业界常见：JWT 只负责 AuthN（你是谁），这里负责 AuthZ 上下文（你能看什么）。
    未来改成查数据库/权限服务即可。
    """
    user_id = user["user_id"]
    roles = user.get("roles", [])
    allowed_dept_keys = _DEMO_ALLOWED_DEPT_KEYS.get(user_id, [])  # 查 DB/权限服务

    return {
        "user_id": user_id,
        "roles": roles,
        "allowed_dept_keys": allowed_dept_keys,
    }