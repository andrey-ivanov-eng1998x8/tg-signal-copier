import time
import pytest
from tg_signal_copier.storage import SQLiteStorage


@pytest.fixture
def storage(tmp_path):
    db_file = tmp_path / "test_signals.db"
    store = SQLiteStorage(str(db_file), dedup_window_seconds=10)
    store.init_db()
    return store


