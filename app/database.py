from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from app.config import Settings


@contextmanager
def database_connection(settings: Settings) -> Iterator[Connection]:
    """Open a transaction-scoped connection when the database is configured."""
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(settings.database_url, connect_timeout=5) as connection:
        yield connection
