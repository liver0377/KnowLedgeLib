import re

SQL_FENCE_RE = re.compile(r"```sql\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

def extract_sql(text: str) -> str:
    """提取回答中的SQL语句"""
    if not text:
        return ""
    m = SQL_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()  # 兜底：如果没 fenced，就当整段是 sql

def ensure_limit(sql: str, limit: int) -> str:
    # 简单策略：如果已有 LIMIT 就不加，否则末尾加 LIMIT
    # 更严谨可以用 sqlglot 修改 AST，这里先给实用版
    low = sql.lower()
    if " limit " in low:
        return sql
    return sql.rstrip().rstrip(";") + f"\nLIMIT {limit};"

from langchain_core.messages import AIMessage

def to_markdown_table(columns, rows, max_cell_len=200):
    # 简单实现：把过长内容截断
    def clip(v):
        s = "" if v is None else str(v)
        return s if len(s) <= max_cell_len else s[:max_cell_len] + "…"

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = "\n".join(
        "| " + " | ".join(clip(r.get(c)) for c in columns) + " |"
        for r in rows
    )
    return "\n".join([header, sep, body]) if body else "\n".join([header, sep])




