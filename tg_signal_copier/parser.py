from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class ParsedSignal:
    """Represents a trading signal parsed from arbitrary Telegram channel copy."""
    symbol: str
    side: str
    entry_min: float | None
    entry_max: float | None
    entries: list[float] = field(default_factory=list)
    take_profits: list[float] = field(default_factory=list)
    stop_loss: float | None = None
    lev_ratio: int | None = None
    confidence: float = 0.0
    raw_text: str = ""


KNOWN_QUOTES = ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH")
CLEANUP_RE = re.compile(r"[\u2700-\u27BF\uE000-\uF8FF\uD83C-\uDBFF\uDC00-\uDFFF]+")

SIDE_RE = re.compile(r"\b(LONG|SHORT|BUY|SELL)\b", re.IGNORECASE)
# Handles #BTC/USDT, BTC-USDT, BTCUSDT, and spaced pairs like BTC USDT
SYMBOL_LINE_RE = re.compile(r"(?:#|\b)([A-Z0-9]{2,10})[/_\- ]?(USDT|USDC|BUSD|USD|BTC|ETH)\b", re.IGNORECASE)
GENERIC_PAIR_RE = re.compile(r"#([A-Z0-9]{2,10})")

# Also match perpetual indicators, e.g. ETHPERP or BTC.P
PERP_SUFFIX_RE = re.compile(r"^([A-Z0-9]+)(?:\.P|PERP)$", re.IGNORECASE)

RANGE_ENTRY_RE = re.compile(
    r"(?:ENTRY|ENTRIES|BUY(?:ING)?(?:\s*ZONE)?)\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:-|–|to)\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
SINGLE_ENTRY_RE = re.compile(
    r"(?:ENTRY|ENTRIES|BUY(?:ING)?(?:\s*ZONE)?)\s*(?:\d*\s*[:=-]|@)?\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)

TP_LINE_RE = re.compile(
    r"(?:TP|TARGET|TAKE\s*PROFIT)\s*\d*\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
SL_LINE_RE = re.compile(
    r"(?:SL|STOP|STOP\s*LOSS)\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
LEV_RE = re.compile(r"(?:LEVERAGE|LEV)\s*[:=-]?\s*(?:CROSS|ISOLATED)?\s*([0-9]{1,3})\s*X?", re.IGNORECASE)


def _clean_text(raw: str) -> str:
    nfkd = unicodedata.normalize("NFKD", raw)
    no_emojis = CLEANUP_RE.sub(" ", nfkd)
    return no_emojis.replace("*", "").replace("`", "").replace("_", " ")


def _extract_symbol(cleaned: str) -> str | None:
    match = SYMBOL_LINE_RE.search(cleaned)
    if match:
        base = match.group(1).upper()
        quote = match.group(2).upper()
        # guard against weird false positives like ENTRYUSDT
        if base in ("ENTRY", "BUY", "SELL", "LONG", "SHORT"):
            return None
        return f"{base}{quote}"

    # Fallback for solitary hashtag tokens like #SOL or #ETHPERP
    generic = GENERIC_PAIR_RE.search(cleaned)
    if generic:
        tag = generic.group(1).upper()
        perp_m = PERP_SUFFIX_RE.match(tag)
        if perp_m:
            tag = f"{perp_m.group(1)}USDT"
        elif not any(tag.endswith(q) for q in KNOWN_QUOTES) and len(tag) <= 6:
            tag = f"{tag}USDT"
        return tag
    return None


def parse_signal(raw_text: str) -> ParsedSignal | None:
    if not raw_text or len(raw_text.strip()) < 8:
        return None

    text = _clean_text(raw_text)
    # print(f"DEBUG: cleaned signal text: {text}")

    side_match = SIDE_RE.search(text)
    if not side_match:
        return None

    raw_side = side_match.group(1).upper()
    side = "BUY" if raw_side in ("BUY", "LONG") else "SELL"

    symbol = _extract_symbol(text)
    if not symbol:
        return None

    tps: list[float] = []
    for match in TP_LINE_RE.finditer(text):
        try:
            val = float(match.group(1))
            if val > 0 and val not in tps:
                tps.append(val)
        except ValueError:
            continue

    sl_match = SL_LINE_RE.search(text)
    stop_loss = None
    if sl_match:
        try:
            stop_loss = float(sl_match.group(1))
        except ValueError:
            pass

    entry_min = None
    entry_max = None
    entries: list[float] = []

    range_match = RANGE_ENTRY_RE.search(text)
    if range_match:
        try:
            p1 = float(range_match.group(1))
            p2 = float(range_match.group(2))
            entry_min = min(p1, p2)
            entry_max = max(p1, p2)
            entries = [entry_min, entry_max]
        except ValueError:
            pass
    else:
        for em in SINGLE_ENTRY_RE.finditer(text):
            try:
                ev = float(em.group(1))
                if ev not in entries:
                    entries.append(ev)
            except ValueError:
                continue
        if entries:
            entry_min = min(entries)
            entry_max = max(entries)

    lev_ratio = None
    lev_match = LEV_RE.search(text)
    if lev_match:
        try:
            lev_ratio = int(lev_match.group(1))
        except ValueError:
            pass

    # Heuristic scoring to reject noisy chatter in channels
    score = 0.0
    if symbol: score += 0.3
    if side: score += 0.2
    if entries or entry_min is not None: score += 0.25
    if tps: score += 0.15
    if stop_loss is not None: score += 0.1

    if score < 0.5:
        return None

    return ParsedSignal(
        symbol=symbol,
        side=side,
        entry_min=entry_min,
        entry_max=entry_max,
        entries=entries,
        take_profits=tps,
        stop_loss=stop_loss,
        lev_ratio=lev_ratio,
        confidence=round(min(score, 1.0), 2),
        raw_text=raw_text,
    )
