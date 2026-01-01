from __future__ import annotations
from dataclasses import dataclass
import sqlglot
from sqlglot import exp

@dataclass
class ValidationResult:
    ok: bool
    normalized_sql: str = ""
    error: str = ""

def validate_sql_(sql: str, dialect: str | None = None) -> ValidationResult:
    """使用sqlglot规范化sql语句, 并确保SQL语句权限仅限于SELECT"""
    sql = (sql or "").strip()
    if not sql:
        return ValidationResult(ok=False, error="Empty SQL")

    try:
        tree = sqlglot.parse_one(sql, read=dialect)  # dialect 可为空
    except Exception as e:
        return ValidationResult(ok=False, error=f"Parse error: {e}")

    # 只读约束：允许 Select / Union / With(最终还是Select/Union) 等
    if isinstance(tree, exp.Select) or isinstance(tree, exp.Union):
        pass
    elif isinstance(tree, exp.With):
        # WITH ... SELECT
        if not isinstance(tree.this, (exp.Select, exp.Union)):
            return ValidationResult(ok=False, error="Only SELECT queries are allowed (WITH must end with SELECT).")
    else:
        return ValidationResult(ok=False, error=f"Only SELECT queries are allowed, got: {type(tree).__name__}")

    # 规范化输出（可选：转成目标方言）
    normalized = tree.sql(dialect=dialect) if dialect else tree.sql()
    return ValidationResult(ok=True, normalized_sql=normalized, error="")