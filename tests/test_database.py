from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.database import database_connection


def test_missing_database_url() -> None:
    with (
        pytest.raises(RuntimeError, match="DATABASE_URL is not configured"),
        database_connection(Settings(database_url=None)),
    ):
        pass


def test_connection_is_closed_after_use() -> None:
    connection = MagicMock()
    with patch("app.database.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        with database_connection(Settings(database_url="postgresql://localhost/test")) as actual:
            assert actual is connection
        connect.assert_called_once_with("postgresql://localhost/test", connect_timeout=5)
        connect.return_value.__exit__.assert_called_once_with(None, None, None)
