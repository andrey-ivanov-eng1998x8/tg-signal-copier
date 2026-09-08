import argparse
import asyncio
import logging
import os
import signal
import sys
from tg_signal_copier.config import load_config
from tg_signal_copier.client import SignalListener
from tg_signal_copier.parser import parse_signal

logger = logging.getLogger("tg_signal_copier")


def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-copier",
        description="Scrape signals from Telegram channels and forward to webhooks",
    )
    parser.add_argument(
        "-c", "--config",
        default=os.getenv("TG_COPIER_CONFIG", "config.yaml"),
        help="Path to configuration YAML file",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set console logging verbosity",
    )
    parser.add_argument(
        "--test-parse",
        metavar="TEXT",
        help="Test parser against a raw message string without connecting to Telegram",
    )
    return parser


async def _run(config_path: str):
    cfg = load_config(config_path)
    listener = SignalListener(cfg)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_signal():
        logger.info("Shutdown signal received, draining tasks...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows fallback
            signal.signal(sig, lambda *_: _on_signal())

    await listener.start()
    await stop_event.wait()

    # FIXME: telethon event loop sometimes hangs on SIGINT if sqlite lock is held
    try:
        await asyncio.wait_for(listener.stop(), timeout=8.0)
    except asyncio.TimeoutError:
        logger.warning("Listener stop timed out after 8s, forcing exit")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.test_parse:
        # print(f"DEBUG raw input: {args.test_parse!r}")
        result = parse_signal(args.test_parse)
        if result:
            print(result.model_dump_json(indent=2))
            return 0
        print("Failed to parse signal from input text.", file=sys.stderr)
        return 1

    logger.info("Starting tg-signal-copier using config=%s", args.config)

    try:
        asyncio.run(_run(args.config))
        return 0
    except (KeyboardInterrupt, SystemExit):
        return 0
    except Exception as e:
        logger.exception("Fatal error in runner: %s", e)
        return 1
