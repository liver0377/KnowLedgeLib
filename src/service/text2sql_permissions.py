"""
Text2SQL 权限管理和数据脱敏模块
提供列级权限控制和敏感数据脱敏功能
"""

import logging
import re
from typing import Optional, Dict, List, Any
from sqlglot import parse_one
from sqlglot.expressions import Table, Column, Select

logger = logging.getLogger(__name__)


class Text2SQLPermissionDAO:
    """Text2SQL 权限管理数据访问对象"""

    @staticmethod
    def get_column_sensitivity(db_name: str, table_name: str, column_name: str) -> str:
        """
        获取列的敏感级别

        Args:
            db_name: 数据库名称
            table_name: 表名
            column_name: 列名

        Returns:
            敏感级别: 'public', 'internal', 'pii', 'sensitive'
        """
        from service.db import get_db_connection

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT sensitivity_level 
                        FROM column_sensitivity_tags
                        WHERE database_name = %s AND table_name = %s AND column_name = %s
                    """,
                        (db_name, table_name, column_name),
                    )
                    result = cursor.fetchone()
                    return result[0] if result else "public"
        except Exception as e:
            logger.error(f"Failed to get column sensitivity: {e}")
            return "public"

    @staticmethod
    def get_table_columns_sensitivity(db_name: str, table_name: str) -> Dict[str, str]:
        """
        获取表中所有列的敏感级别

        Args:
            db_name: 数据库名称
            table_name: 表名

        Returns:
            字典: {列名: 敏感级别}
        """
        from service.db import get_db_connection

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT column_name, sensitivity_level
                        FROM column_sensitivity_tags
                        WHERE database_name = %s AND table_name = %s
                    """,
                        (db_name, table_name),
                    )
                    return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Failed to get table columns sensitivity: {e}")
            return {}

    @staticmethod
    def get_allowed_tables_for_user(db_name: str, user_roles: List[str]) -> List[str]:
        """
        获取用户可访问的表列表

        策略:
        - admin: 可访问所有表
        - analyst: 只能访问 public 和 internal 级别的列所在的表
        - member: 不能使用 text2sql (在 API 层拦截)

        Args:
            db_name: 数据库名称
            user_roles: 用户角色列表

        Returns:
            表名列表，空列表表示无限制
        """
        from service.db import get_db_connection

        # admin 无限制
        if "admin" in user_roles:
            return []

        # analyst 只能访问非敏感数据
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT DISTINCT table_name 
                        FROM column_sensitivity_tags
                        WHERE database_name = %s
                        AND sensitivity_level IN ('public', 'internal')
                    """,
                        (db_name,),
                    )
                    return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get allowed tables: {e}")
            return []


def mask_query_result(
    result: List[Dict[str, Any]], db_name: str, table_name: str, user_roles: List[str] = None
) -> List[Dict[str, Any]]:
    """
    对查询结果进行列脱敏

    策略:
    - admin: 不脱敏
    - analyst: 脱敏 pii 和 sensitive 列
    - public/internal: 不脱敏

    Args:
        result: 查询结果列表
        db_name: 数据库名称
        table_name: 表名
        user_roles: 用户角色列表

    Returns:
        脱敏后的查询结果
    """
    if not result:
        return result

    # admin 不脱敏
    if user_roles and "admin" in user_roles:
        return result

    # 获取列的敏感级别
    sensitivity_map = Text2SQLPermissionDAO.get_table_columns_sensitivity(db_name, table_name)

    if not sensitivity_map:
        return result

    masked_result = []
    for row in result:
        masked_row = {}
        for col, val in row.items():
            if col in sensitivity_map:
                level = sensitivity_map[col]
                if level == "pii" and val:
                    masked_row[col] = mask_pii(val)
                elif level == "sensitive" and val:
                    masked_row[col] = "[SENSITIVE]"
                else:
                    masked_row[col] = val
            else:
                masked_row[col] = val
        masked_result.append(masked_row)

    return masked_result


def mask_pii(value: Any) -> str:
    """
    PII 数据部分遮蔽

    保留前几位和后几位，中间用 **** 替换

    Args:
        value: 需要脱敏的值

    Returns:
        脱敏后的字符串

    Examples:
        >>> mask_pii('zhangsan@example.com')
        'zh***com'
        >>> mask_pii('13812345678')
        '13***78'
    """
    if not value:
        return value

    val_str = str(value)
    val_str = val_str.strip()

    if len(val_str) <= 4:
        return "****"
    elif len(val_str) <= 8:
        head_len = 2
        tail_len = 2
    else:
        head_len = 3
        tail_len = 4

    return f"{val_str[:head_len]}****{val_str[-tail_len:]}"


def mask_sensitive(value: Any) -> str:
    """
    敏感数据遮蔽

    完全隐藏敏感数据，替换为占位符

    Args:
        value: 需要隐藏的值

    Returns:
        占位符字符串
    """
    if not value:
        return value
    return "[SENSITIVE]"


def extract_table_name_from_sql(sql: str) -> Optional[str]:
    """
    从 SQL 查询中提取主表名

    Args:
        sql: SQL 查询字符串

    Returns:
        主表名，如果无法提取则返回 None
    """
    try:
        parsed = parse_one(sql, dialect="mysql")

        if isinstance(parsed, Select):
            # 获取 FROM 子句中的表
            from_tables = parsed.find_all(Table)
            if from_tables:
                # 返回第一个表名
                return str(from_tables[0].this)

        return None
    except Exception as e:
        logger.error(f"Failed to extract table name from SQL: {e}")
        return None


def extract_columns_from_sql(sql: str) -> List[str]:
    """
    从 SQL 查询中提取所有列名

    Args:
        sql: SQL 查询字符串

    Returns:
        列名列表
    """
    try:
        parsed = parse_one(sql, dialect="mysql")

        if isinstance(parsed, Select):
            columns = []
            for col in parsed.find_all(Column):
                columns.append(str(col.this))
            return columns

        return []
    except Exception as e:
        logger.error(f"Failed to extract columns from SQL: {e}")
        return []


def validate_sql_limit(
    sql: str, default_limit: int = 2000, max_limit: int = 10000
) -> tuple[bool, str, int]:
    """
    验证 SQL 查询的 LIMIT 子句

    规则:
    1. 必须包含 LIMIT
    2. LIMIT 值不能超过 max_limit
    3. 如果没有 LIMIT，自动添加 default_limit

    Args:
        sql: SQL 查询字符串
        default_limit: 默认 LIMIT 值
        max_limit: 最大允许的 LIMIT 值

    Returns:
        (是否有效, 错误信息, 使用的 LIMIT 值)
    """
    sql_upper = sql.upper()

    # 检查是否包含 LIMIT
    limit_match = re.search(r"\bLIMIT\s+(\d+)", sql_upper)

    if limit_match:
        limit = int(limit_match.group(1))

        if limit > max_limit:
            return False, f"LIMIT 不能超过 {max_limit}", limit

        return True, "", limit
    else:
        # 没有 LIMIT，需要添加
        return True, f"自动添加 LIMIT {default_limit}", default_limit


def add_limit_to_sql(sql: str, limit: int) -> str:
    """
    为 SQL 查询添加 LIMIT 子句

    Args:
        sql: SQL 查询字符串
        limit: LIMIT 值

    Returns:
        添加了 LIMIT 的 SQL 查询
    """
    sql = sql.strip()

    # 如果已经有 LIMIT，替换它
    limit_pattern = re.compile(r"\bLIMIT\s+\d+\s*;?$", re.IGNORECASE)
    if limit_pattern.search(sql):
        sql = limit_pattern.sub(f" LIMIT {limit}", sql)
        return sql.rstrip(";") + ";"

    # 移除结尾的分号
    sql = sql.rstrip(";")

    # 添加 LIMIT
    return f"{sql} LIMIT {limit};"


def check_sql_type_restrictions(sql: str) -> tuple[bool, str]:
    """
    检查 SQL 类型限制（只允许 SELECT）

    Args:
        sql: SQL 查询字符串

    Returns:
        (是否有效, 错误信息)
    """
    sql_upper = sql.strip().upper()

    # 禁止的关键字
    forbidden_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
    ]

    for keyword in forbidden_keywords:
        if f" {keyword} " in f" {sql_upper} " or sql_upper.startswith(keyword):
            return False, f"禁止使用 {keyword} 操作，只允许 SELECT 查询"

    # 检查是否为 SELECT
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        return False, "只允许 SELECT 查询"

    # 检查多语句（分号，除结尾外）
    # 移除结尾的分号后检查是否还有其他分号
    sql_trimmed = sql.rstrip(";").strip()
    if ";" in sql_trimmed:
        return False, "禁止执行多条 SQL 语句"

    return True, ""


def get_allowed_databases_for_user(user_roles: List[str], permissions: set) -> List[str]:
    """
    根据用户角色和权限获取可访问的数据库列表

    规则:
    - admin: ['ecommerce'] (原始数据库)
    - analyst: ['ecommerce'] (只能访问视图)
    - member: [] (不能使用 text2sql)

    Args:
        user_roles: 用户角色列表
        permissions: 用户权限集合

    Returns:
        可访问的数据库名称列表
    """
    from core import settings

    allowed_dbs = []

    # admin 可以查询原始数据库
    if "admin" in user_roles:
        allowed_dbs.append(settings.DEFAULT_DB)

    # analyst 只能查询 analytics (通过视图)
    if "analyst" in user_roles and "text2sql:query_analytics" in permissions:
        allowed_dbs.append(settings.DEFAULT_DB)

    return allowed_dbs


def should_use_analytics_views(user_roles: List[str], permissions: set) -> bool:
    """
    判断是否应该使用 analytics 视图（而不是原始表）

    规则:
    - admin: False (直接查询原始表)
    - analyst: True (只能查询脱敏视图)
    - member: False (不能使用 text2sql)

    Args:
        user_roles: 用户角色列表
        permissions: 用户权限集合

    Returns:
        是否使用 analytics 视图
    """
    if "analyst" in user_roles and "text2sql:query_analytics" in permissions:
        return True
    return False


def convert_to_analytics_view(sql: str) -> str:
    """
    将原始表名转换为 analytics 视图名

    规则:
    - users -> v_analytics_users
    - orders -> v_analytics_orders
    - products -> v_analytics_products
    - 等等...

    Args:
        sql: SQL 查询字符串

    Returns:
        转换后的 SQL 查询
    """
    from core import settings

    table_mapping = {
        "users": "v_analytics_users",
        "orders": "v_analytics_orders",
        "products": "v_analytics_products",
        "order_items": "v_analytics_order_items",
    }

    sql_lower = sql.lower()

    for original_table, view_table in table_mapping.items():
        # 替换 FROM 子句中的表名
        pattern = re.compile(r"\bFROM\s+" + re.escape(original_table) + r"\b", re.IGNORECASE)
        sql = pattern.sub(f"FROM {view_table}", sql)

        # 替换 JOIN 子句中的表名
        pattern = re.compile(
            r"\b(?:INNER|LEFT|RIGHT|FULL)\s+JOIN\s+" + re.escape(original_table) + r"\b",
            re.IGNORECASE,
        )
        sql = pattern.sub(f"JOIN {view_table}", sql)

    return sql
