from typing import Any

# demo：先写死。生产改成查 RBAC 表/Redis 缓存
def get_allowed_dept_keys(user: dict[str, Any]) -> list[str]:
    roles = set(user.get("roles", []) or [])
    user_id = user.get("user_id", "")

    if "admin" in roles:
        return ["AI", "database", "micro_service"]  # demo：所有部门
    if user_id == "user-ryan":
        return ["micro_service"]  # demo

    return []
