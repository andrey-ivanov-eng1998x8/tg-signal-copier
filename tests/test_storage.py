import time
import pytest
from tg_signal_copier.storage import SQLiteStorage


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_signals.db")


def test_record_and_is_duplicate(db_path):
    store = SQLiteStorage(db_path, dedup_window_seconds=2)
    store.init_db()

    msg_id = 1001
    channel_id = -100123456789
    sig_hash = "hash_btc_buy_64000"

    # First time seeing it
    assert store.is_duplicate(channel_id, msg_id, sig_hash) is False
    store.record_signal(channel_id, msg_id, sig_hash, "BTCUSDT", "BUY")

    # Same message id
    assert store.is_duplicate(channel_id, msg_id, sig_hash) is True

    # Different message id but identical payload hash
    assert store.is_duplicate(channel_id, 1002, sig_hash) is True

    # Different channel, same hash -> should not dedup cross-channel by default
    assert store.is_duplicate(-100999999, 1001, sig_hash) is False
    store.close()


def test_dedup_window_expiration(db_path):
    # 1 second window for fast testing
    store = SQLiteStorage(db_path, dedup_window_seconds=1)
    store.init_db()

    channel_id = -10011111
    sig_hash = "quick_expire_test"

    store.record_signal(channel_id, 501, sig_hash, "SOLUSDT", "SELL")
    assert store.is_duplicate(channel_id, 502, sig_hash) is True

    # Wait out the window
    time.sleep(1.2)
    # After window passes, new message with same signal hash is treated as fresh
    assert store.is_duplicate(channel_id, 503, sig_hash) is False
    store.close()


def test_state_persists_across_reopen(db_path):
    store1 = SQLiteStorage(db_path, dedup_window_seconds=300)
    store1.init_db()
    store1.record_signal(-100222, 999, "persisted_hash", "ETHUSDT", "BUY")
    store1.close()

    # Re-open same db file
    store2 = SQLiteStorage(db_path, dedup_window_seconds=300)
    store2.init_db()
    assert store2.is_duplicate(-100222, 999, "persisted_hash") is True
    assert store2.is_duplicate(-100222, 1000, "persisted_hash") is True
    store2.close()
