# tg-signal-copier

Small daemon that listens to Telegram channels via userbot session (Telethon), extracts trade signals from freeform text messages, deduplicates them, and posts clean JSON payloads to downstream webhooks.

I built this because most copier bots are clunky SaaS apps or require full account takeover. This just runs in a tmux session or systemd unit, keeps a local sqlite db to prevent duplicate execution on channel edits, and sends execution latencies to a local prometheus endpoint.

## Requirements

- Python 3.11+
- Telegram API credentials (api_id and api_hash from my.telegram.org)

## Setup

```bash
git clone https://github.com/author/tg-signal-copier.git
cd tg-signal-copier
python -m venv .venv
source .venv/bin/activate
pip install .
```

Copy the example environment file:

```bash
cp .env.example .env
```

Fill in your `TG_API_ID`, `TG_API_HASH`, and list of channel IDs to watch.

## Usage

First run will ask for Telegram phone verification to create the session file:

```bash
python -m tg_signal_copier --config .env
```

To test parser rules against raw dumped text without running the listener:

```bash
python -m tg_signal_copier parse-test --file sample_signal.txt
```

## License

MIT

<!-- checked: 2026-09-08 -->
