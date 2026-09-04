import argparse
import asyncio
import logging
import os
import signal
import sys
from tg_signal_copier.config import load_config
from tg_signal_copier.client import SignalListener

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
    return parser


