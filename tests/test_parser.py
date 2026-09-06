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


