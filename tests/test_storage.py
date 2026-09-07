import time
import pytest
from tg_signal_copier.storage import SQLiteStorage


@pytest.fixture
def storage(tmp_path):
    db_file = tmp_path / "test_signals.db"
    store = SQLiteStorage(str(db_file), dedup_window_seconds=10)
    store.init_db()
    return store


def test_record_and_is_duplicate(storage):
    msg_id = 1001
    channel_id = -100123456789
    sig_hash = "hash_btc_buy_64000"

    # First time seeing it
    assert storage.is_duplicate(channel_id, msg_id, sig_hash) is False
    storage.record_signal(channel_id, msg_id, sig_hash, "BTCUSDT", "BUY")

    # Same message id
    assert storage.is_duplicate(channel_id, msg_id, sig_hash) is True

    # Different message id but same signal hash within window
    assert storage.is_duplicate(channel_id, 1002, sig_hash) is True

    # Different signal hash in same channel
    assert storage.is_duplicate(channel_id, 1003, "hash_eth_buy_3000") is False
