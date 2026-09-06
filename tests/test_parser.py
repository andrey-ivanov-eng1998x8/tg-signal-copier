import pytest
from tg_signal_copier.parser import parse_signal, ParsedSignal


def test_clean_buy_signal():
    raw = """
    BUY BTCUSDT
    Entry: 64200 - 64500
    TP1: 65100
    TP2: 66000
    SL: 63800
    """
    sig = parse_signal(raw)
    assert sig is not None
    assert sig.symbol == "BTCUSDT"
    assert sig.action == "BUY"
    assert sig.entry_min == 64200.0
    assert sig.entry_max == 64500.0
    assert sig.take_profits == [65100.0, 66000.0]
    assert sig.stop_loss == 63800.0


def test_clean_short_signal():
    raw = """
    #ETH/USDT SHORT
    Entry: 3450.5
    Targets: 3400, 3350, 3200
    Stoploss: 3520
    """
    sig = parse_signal(raw)
    assert sig is not None
    assert sig.symbol == "ETHUSDT"
    assert sig.action == "SELL"
    assert sig.entry_min == 3450.5
    assert sig.entry_max == 3450.5
    assert sig.take_profits == [3400.0, 3350.0, 3200.0]
    assert sig.stop_loss == 3520.0


def test_ignore_chat_noise():
    assert parse_signal("Good morning guys! Big day ahead 🚀") is None
    assert parse_signal("Check out our VIP channel for 90% winrate") is None
