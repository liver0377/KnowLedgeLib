# service/auth.py
"""
权限认证和授权模块
提供基于RBAC和ABAC的权限管理
"""
import time
from typing import Any, Callable, TypedDict, Optional
from threading import Lock
from functools import lru_cache

import jwt
from jwt import PyJWTError
from fastapi import Request, Depends, HTTPException, status

from core import settings
from service.db import RBACDAO

logger = __import__('logging').getLogger(__name__)


# ==============================
# 角色常量（这些常量用于JWT验证，需要保留）
# ==============================
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

ALL_ROLES = {ROLE_ADMIN, ROLE_MEMBER}


# ==============================
# 权限管理器（从数据库动态加载权限）
# ==============================
class PermissionManager:
    """
    权限管理器：从数据库加载和管理权限常量
    使用单例模式和缓存机制，避免频繁查询数据库
    """
    _instance = None
    _lock = Lock()
    _initialized = False
    _permissions_cache: dict[str, dict] = {}
    _cache_timestamp: float = 0
    _cache_ttl = 300  # 缓存有效期（秒），默认5分钟
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def reload(cls) -> None:
        """强制重新加载权限缓存"""
        with cls._lock:
            cls._initialized = False
            cls._permissions_cache = {}
            cls._cache_timestamp = 0
            logger.info("Permission cache cleared, will reload on next access")
    
    def _load_permissions(self) -> None:
        """从数据库加载权限到缓存"""
        if self._initialized and (time.time() - self._cache_timestamp) < self._cache_ttl:
            return  # 缓存未过期
        
        with self._lock:
            # 双重检查，避免重复加载
            if self._initialized and (time.time() - self._cache_timestamp) < self._cache_ttl:
                return
            
            try:
                permissions = RBACDAO.get_all_permissions()
                self._permissions_cache = {
                    perm['perm_key']: perm for perm in permissions
                }
                self._cache_timestamp = time.time()
                self._initialized = True
                logger.info(f"Loaded {len(self._permissions_cache)} permissions from database")
            except Exception as e:
                logger.error(f"Failed to load permissions from database: {e}")
                # 如果加载失败，保留旧缓存
                if not self._initialized:
                    self._permissions_cache = {}
                    self._cache_timestamp = time.time()
                    self._initialized = True
    
    def get_permission_key(self, resource: str, action: str) -> Optional[str]:
        """
        根据资源和操作获取权限标识
        例如: get_permission_key("kb", "file:list") 返回 "kb:file:list"
        
        Args:
            resource: 资源类型，如 "kb", "admin"
            action: 操作类型，如 "file:list", "user:update"
        
        Returns:
            权限标识字符串，如果未找到返回 None
        """
        self._load_permissions()
        
        perm_key = f"{resource}:{action}"
        if perm_key in self._permissions_cache:
            return perm_key
        
        return None
    
    def has_permission(self, user: dict[str, Any], resource: str, action: str) -> bool:
        """
        检查用户是否具有指定权限
        
        Args:
            user: 用户上下文字典（包含 permissions 字段）
            resource: 资源类型
            action: 操作类型
        
        Returns:
            True 如果用户有权限，False 否则
        """
        perm_key = self.get_permission_key(resource, action)
        if not perm_key:
            logger.warning(f"Permission key not found for {resource}:{action}")
            return False
        
        permissions = user.get("permissions", set())
        return perm_key in permissions
    
    def require_permission(self, user: dict[str, Any], resource: str, action: str) -> None:
        """
        检查用户权限，如果没有权限则抛出 HTTPException
        
        Args:
            user: 用户上下文字典
            resource: 资源类型
            action: 操作类型
        
        Raises:
            HTTPException: 如果用户没有权限，抛出 403 错误
        """
        if not self.has_permission(user, resource, action):
            perm_key = f"{resource}:{action}"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {perm_key}"
            )
    
    def get_all_permission_keys(self) -> list[str]:
        """获取所有权限标识列表"""
        self._load_permissions()
        return list(self._permissions_cache.keys())
    
    def get_permission_info(self, perm_key: str) -> Optional[dict]:
        """获取权限详细信息"""
        self._load_permissions()
        return self._permissions_cache.get(perm_key)


# 全局权限管理器实例
permission_manager = PermissionManager()


# ==============================
# JWT 认证相关函数
# ==============================
def jwt_secret() -> str:
    return settings.JWT_SECRET.get_secret_value()  # type: ignore[attr-defined]


def create_access_token(*, sub: str, roles: list[str]) -> str:
    """
    生成 JWT (AuthN)
    roles：只允许 member/admin，其他一律过滤掉，避免脏数据/越权注入
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

    # roles 清洗：只保留标准角色
    if not isinstance(roles, list):
        roles = []
    roles = [r for r in roles if isinstance(r, str) and r in ALL_ROLES]

    return {"user_id": sub, "roles": roles}


# ==============================
# 用户上下文和权限检查
# ==============================
class UserContext(TypedDict):
    user_id: str
    roles: list[str]
    allowed_dept_keys: list[str]
    permissions: set[str]


def get_user_context(user: dict[str, Any] = Depends(get_current_user)) -> UserContext:
    """
    AuthZ 上下文（你能看什么）：
    - user_id/roles 来自 JWT
    - allowed_dept_keys 来自数据库（用户可访问的部门）
    - permissions 来自数据库（用户的所有权限点）
    """
    user_id = user["user_id"]
    roles = user.get("roles", []) or []
    
    # 从数据库获取用户权限
    try:
        permissions = RBACDAO.get_user_permissions(int(user_id))
        dept_access = RBACDAO.get_user_departments(int(user_id))
        allowed_dept_keys = [d['dept_key'] for d in dept_access if d['can_read']]
    except Exception as e:
        # 数据库查询失败，使用空权限（安全第一）
        logger.error(f"Failed to load user context from database: {e}")
        permissions = set()
        allowed_dept_keys = []
    
    return {
        "user_id": user_id,
        "roles": roles,
        "allowed_dept_keys": allowed_dept_keys,
        "permissions": permissions,
    }


def has_role(user: dict[str, Any], role: str) -> bool:
    """检查用户是否具有指定角色"""
    return role in (user.get("roles") or [])


def require_admin(user: dict[str, Any]) -> None:
    """检查用户是否有管理员权限，没有则抛出 403 异常"""
    if not has_role(user, ROLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def can_access_dept(user: dict[str, Any], dept_key: str) -> bool:
    """
    Dept Scope（读权限）：list/detail/download/search 统一使用
    从数据库查询用户可访问的部门，检查 can_read 字段
    """
    # admin不受部门限制
    if has_role(user, ROLE_ADMIN):
        return True
    
    # 检查用户是否对该部门有读权限
    try:
        dept_access = RBACDAO.get_user_departments(int(user["user_id"]))
        for dept in dept_access:
            if dept['dept_key'] == dept_key and dept['can_read']:
                return True
    except Exception as e:
        logger.error(f"Failed to check department read permission: {e}")
    return False


def can_write_dept(user: dict[str, Any], dept_key: str) -> bool:
    """
    Dept Scope（写权限）：upload/edit/delete 统一使用
    从数据库查询用户的部门写权限，检查 can_write 字段
    - admin：任意 dept
    - member：仅对有写权限的部门（can_write=1）
    """
    if has_role(user, ROLE_ADMIN):
        return True
    
    # 检查用户是否对该部门有写权限
    try:
        dept_access = RBACDAO.get_user_departments(int(user["user_id"]))
        for dept in dept_access:
            if dept['dept_key'] == dept_key and dept['can_write']:
                return True
    except Exception as e:
        logger.error(f"Failed to check department write permission: {e}")
    return False


def require_permission(perm: str) -> Callable:
    """
    FastAPI dependency 版本：用于 endpoint 上声明 "必须具备某权限点"
    注意：这个函数现在已废弃，建议使用 permission_manager.require_permission()
    """
    def _dep(ctx: dict[str, Any] = Depends(get_user_context)) -> dict[str, Any]:
        permissions = ctx.get("permissions", set())
        if perm not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return ctx
    return _dep
