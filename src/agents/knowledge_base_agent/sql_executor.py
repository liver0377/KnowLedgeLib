from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# import logging
# logger = logging.getLogger(__name__)


@dataclass
class ExecResult:
    ok: bool
    columns: list[str] = None
    rows: list[dict[str, Any]] = None
    rowcount: int = 0
    error: str = ""


def get_mysql_connection_string() -> str:
    from core.settings import settings

    if not all(
        [
            settings.MYSQL_HOST,
            settings.MYSQL_PORT,
            settings.MYSQL_USER,
            settings.MYSQL_PASSWORD,
            settings.TARGET_DB,
        ]
    ):
        raise ValueError(
            "MySQL connection requires MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DB environment variables"
        )

    password = quote_plus(settings.MYSQL_PASSWORD.get_secret_value())
    return (
        f"mysql+pymysql://{settings.MYSQL_USER}:{password}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.TARGET_DB}"
        f"?charset={settings.MYSQL_CHARSET}"
    )


def get_postgres_connection_string() -> str:
    from core.settings import settings

    if not all(
        [
            settings.POSTGRES_HOST,
            settings.POSTGRES_PORT,
            settings.POSTGRES_USER,
            settings.POSTGRES_PASSWORD,
            settings.POSTGRES_DB,
        ]
    ):
        raise ValueError(
            "PostgreSQL connection requires POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB environment variables"
        )

    password = quote_plus(settings.POSTGRES_PASSWORD.get_secret_value())
    return (
        f"postgresql://{settings.POSTGRES_USER}:{password}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        f"?application_name={settings.POSTGRES_APPLICATION_NAME}"
    )


def get_sqlite_connection_string() -> str:
    from core.settings import settings

    return f"sqlite:///{settings.SQLITE_DB_PATH}"


def get_engine():
    from core.settings import DatabaseType, settings

    db_type = settings.TRANSACTION_DATABASE_TYPE

    connection_string_builders = {
        DatabaseType.MYSQL: get_mysql_connection_string,
        DatabaseType.POSTGRES: get_postgres_connection_string,
        DatabaseType.SQLITE: get_sqlite_connection_string,
    }

    if db_type not in connection_string_builders:
        raise ValueError(
            f"Unsupported TRANSACTION_DATABASE_TYPE: {db_type}. "
            f"Supported types: {[t.value for t in connection_string_builders.keys()]}"
        )

    url = connection_string_builders[db_type]()

    print(f"url: {url}")

    return create_engine(url, pool_pre_ping=True)


def execute_select(sql: str, timeout_s: int = 10, max_rows: int = 200) -> ExecResult:
    eng = get_engine()
    try:
        with eng.connect() as conn:
            res = conn.execute(text(sql))
            cols = list(res.keys())
            fetched = res.fetchmany(max_rows)
            rows = [dict(zip(cols, r)) for r in fetched]
            return ExecResult(ok=True, columns=cols, rows=rows, rowcount=len(rows))
    except Exception as e:
        return ExecResult(ok=False, error=str(e))
