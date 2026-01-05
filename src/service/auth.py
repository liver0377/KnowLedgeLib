# service/auth.py
import time
from typing import Any, Callable, TypedDict

import jwt
from jwt import PyJWTError
from fastapi import Request, Depends, HTTPException, status

from core import settings

# -----------------------------
# 1) Role + Permission constants
# -----------------------------
ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"

ALL_ROLES = {ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER}

# 你可以按需扩展权限点（建议保持稳定字符串）
PERM_KB_FILE_LIST = "kb:file:list"
PERM_KB_FILE_DETAIL = "kb:file:detail"
PERM_KB_FILE_DOWNLOAD = "kb:file:download"
PERM_KB_FILE_UPLOAD = "kb:file:upload"

PERM_ADMIN_USER_LIST = "admin:user:list"
PERM_ADMIN_USER_UPDATE = "admin:user:update"

ROLE_PERMS: dict[str, set[str]] = {
    ROLE_ADMIN: {
        PERM_KB_FILE_LIST, PERM_KB_FILE_DETAIL, PERM_KB_FILE_DOWNLOAD, PERM_KB_FILE_UPLOAD,
        PERM_ADMIN_USER_LIST, PERM_ADMIN_USER_UPDATE,
    },
    ROLE_EDITOR: {
        PERM_KB_FILE_LIST, PERM_KB_FILE_DETAIL, PERM_KB_FILE_DOWNLOAD, PERM_KB_FILE_UPLOAD,
    },
    ROLE_VIEWER: {
        PERM_KB_FILE_LIST, PERM_KB_FILE_DETAIL, PERM_KB_FILE_DOWNLOAD,
    },
}

# -----------------------------
# 2) Demo dept scopes (replace with DB later)
# -----------------------------
_DEMO_ALLOWED_DEPT_KEYS: dict[str, list[str]] = {
    "user-ryan": ["micro_service"],   # admin 实际上不受限，这里留着无所谓
    "user-viewer": ["AI"],
}

def jwt_secret() -> str:
    return settings.JWT_SECRET.get_secret_value()  # type: ignore[attr-defined]


def create_access_token(*, sub: str, roles: list[str]) -> str:
    """
    生成 JWT (AuthN)
    roles：只允许 viewer/editor/admin，其他一律过滤掉，避免脏数据/越权注入
    """
    now = int(time.time())
    clean_roles = [r for r in (roles or []) if r in ALL_ROLES]

    payload = {
        "sub": sub,
        "roles": clean_roles,
        "iat": now,
        "exp": now + settings.JWT_EXPIRES_SECONDS,
    }
    return jwt.encode(payload, jwt_secret(), algorithm=settings.JWT_ALG)


def get_current_user(request: Request) -> dict[str, Any]:
    """从 cookie JWT 解析 AuthN 身份（你是谁）"""
    token = request.cookies.get(settings.JWT_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[settings.JWT_ALG])
    except PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    sub = payload.get("sub")
    roles = payload.get("roles", [])

    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # roles 清洗：只保留三种标准角色
    if not isinstance(roles, list):
        roles = []
    roles = [r for r in roles if isinstance(r, str) and r in ALL_ROLES]

    return {"user_id": sub, "roles": roles}


class UserContext(TypedDict):
    user_id: str
    roles: list[str]
    allowed_dept_keys: list[str]


def get_user_context(user: dict[str, Any] = Depends(get_current_user)) -> UserContext:
    """
    AuthZ 上下文（你能看什么）：
    - user_id/roles 来自 JWT
    - allowed_dept_keys 来自 DB/权限服务（demo 先写死）
    """
    user_id = user["user_id"]
    roles = user.get("roles", []) or []
    allowed_dept_keys = _DEMO_ALLOWED_DEPT_KEYS.get(user_id, [])
    return {
        "user_id": user_id,
        "roles": roles,
        "allowed_dept_keys": allowed_dept_keys,
    }


def has_role(user: dict[str, Any], role: str) -> bool:
    return role in (user.get("roles") or [])


def require_perm(user: dict[str, Any], perm: str) -> None:
    """
    RBAC：检查当前用户是否拥有某权限点
    """
    roles = user.get("roles") or []
    allowed: set[str] = set()
    for r in roles:
        allowed |= ROLE_PERMS.get(r, set())
    if perm not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def can_access_dept(user: dict[str, Any], dept_key: str) -> bool:
    """
    Dept Scope（读权限）：list/detail/download/search 统一使用
    """
    if has_role(user, ROLE_ADMIN):
        return True
    allowed = set(user.get("allowed_dept_keys") or [])
    return dept_key in allowed


def can_upload_dept(user: dict[str, Any], dept_key: str) -> bool:
    """
    Dept Scope（写权限）：upload/edit 统一使用
    - admin：任意 dept
    - editor：仅 allowed_dept_keys 内
    - viewer：不允许（但这个一般由 require_perm(PERM_KB_FILE_UPLOAD) 拦住）
    """
    if has_role(user, ROLE_ADMIN):
        return True
    if has_role(user, ROLE_EDITOR):
        allowed = set(user.get("allowed_dept_keys") or [])
        return dept_key in allowed
    return False


def require_permission(perm: str) -> Callable:
    """
    FastAPI dependency 版本：用于 endpoint 上声明 “必须具备某权限点”
    """
    def _dep(ctx: dict[str, Any] = Depends(get_user_context)) -> dict[str, Any]:
        require_perm(ctx, perm)
        return ctx
    return _dep
