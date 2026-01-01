from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import os
from sqlalchemy import create_engine, text

# import logging
# logger = logging.getLogger(__name__)

@dataclass
class ExecResult:
    ok: bool
    columns: list[str] = None
    rows: list[dict[str, Any]] = None
    rowcount: int = 0
    error: str = ""

def get_engine():
    url = os.getenv("DB_URL")  # 例如 postgres://... 或 mysql+pymysql://...
    if not url:
        raise ValueError("DB_URL env var is required for execute_sql")
    # pool_pre_ping 防止连接断开
    return create_engine(url, pool_pre_ping=True)

def execute_select(sql: str, timeout_s: int = 10, max_rows: int = 200) -> ExecResult:
    # logger.info("execute_select sql=%r max_rows=%r timeout_s=%r", sql, max_rows, timeout_s)
    eng = get_engine()
    try:
        with eng.connect() as conn:
            # 某些 DB 支持 statement_timeout，需要单独设置（可选）
            res = conn.execute(text(sql))
            cols = list(res.keys())
            fetched = res.fetchmany(max_rows)
            rows = [dict(zip(cols, r)) for r in fetched]
            return ExecResult(ok=True, columns=cols, rows=rows, rowcount=len(rows))
    except Exception as e:
        return ExecResult(ok=False, error=str(e))
