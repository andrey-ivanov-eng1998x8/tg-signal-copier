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
    assert parse_signal("BTC looking bullish on the 4h timeframe...") is None


def test_noisy_emoji_packed_format():
    # Real example from a VIP crypto leak channel
    raw = """
    🔥 🔥 VIP SIGNAL 🔥 🔥
    
    Coin: $SOL/USDT (Long 20x-50x)
    
    👉 Entry zone: 134.20 - 136.00
    
    🎯 Target 1 - 138.50
    🎯 Target 2 - 142.00
    🎯 Target 3 - 150.00 🚀
    
    ⛔️ Stop: 129.80
    
    Manage risk! Not financial advice.
    """
    sig = parse_signal(raw)
    assert sig is not None
    assert sig.symbol == "SOLUSDT"
    assert sig.action == "BUY"
    assert sig.entry_min == 134.20
    assert sig.entry_max == 136.00
    assert sig.take_profits == [138.50, 142.00, 150.00]
    assert sig.stop_loss == 129.80


def test_forex_style_pair_and_dots():
    raw = """
    GOLD (XAU/USD)
    SELL NOW @ 2384.50
    TP: 2375.00 / 2360.00
    SL: 2392.10
    """
    sig = parse_signal(raw)
    assert sig is not None
    assert sig.symbol in ("XAUUSD", "GOLD")
    assert sig.action == "SELL"
    assert sig.entry_min == 2384.50
    assert sig.take_profits == [2375.0, 2360.0]
    assert sig.stop_loss == 2392.10


def test_comma_decimals_and_unicode_dashes():
    # European number notation and en-dash inside price ranges
    raw = "LONG BTC/USDT \nENTRY: 60.100,50 – 60.500,00\nTP: 62.000\nSL: 59.200"
    sig = parse_signal(raw)
    assert sig is not None
    assert sig.entry_min == 60100.50
    assert sig.entry_max == 60500.00
    assert sig.take_profits == [62000.0]
    assert sig.stop_loss == 59200.0


def test_missing_stop_loss_still_parses():
    # Some scalpers omit SL or say 'manual SL'
    raw = "BUY PEPEUSDT at 0.0000082 TP: 0.0000095, 0.0000110"
    sig = parse_signal(raw)
    assert sig is not None
    assert sig.symbol == "PEPEUSDT"
    assert sig.stop_loss is None
    assert len(sig.take_profits) == 2
