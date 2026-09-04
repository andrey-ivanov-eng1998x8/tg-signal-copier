from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedSignal:
    symbol: str
    side: str
    entries: list[float]
    take_profits: list[float]
    stop_loss: float | None
    raw_text: str


SYMBOL_RE = re.compile(r"#?([A-Z0-9]{2,10})[/_-]?([A-Z0-9]{2,6})")
SIDE_RE = re.compile(r"\b(LONG|SHORT|BUY|SELL)\b", re.IGNORECASE)
TP_RE = re.compile(r"(?:TP|TARGET)\s*\d*\s*[:=-]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
SL_RE = re.compile(r"(?:SL|STOP(?:\s*LOSS)?)\s*[:=-]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
ENTRY_RE = re.compile(r"(?:ENTRY|BUY\s*ZONE|ENTRY\s*ZONE)\s*[:=-]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def parse_signal(text: str) -> ParsedSignal | None:
    if not text or len(text.strip()) < 10:
        return None

    side_match = SIDE_RE.search(text)
    if not side_match:
        return None
    side = side_match.group(1).upper()
    if side in ("BUY", "LONG"):
        side = "BUY"
    else:
        side = "SELL"

    sym_match = SYMBOL_RE.search(text)
    if not sym_match:
        return None
    symbol = f"{sym_match.group(1)}{sym_match.group(2)}".upper()

    entries = [float(m.group(1)) for m in ENTRY_RE.finditer(text)]
    tps = [float(m.group(1)) for m in TP_RE.finditer(text)]

    sl_match = SL_RE.search(text)
    stop_loss = float(sl_match.group(1)) if sl_match else None

    if not entries and not tps:
        return None

    return ParsedSignal(
        symbol=symbol,
        side=side,
        entries=entries,
        take_profits=tps,
        stop_loss=stop_loss,
        raw_text=text,
    )
