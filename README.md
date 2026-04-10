# Telegram Notes Bot (Python)

A complete Telegram bot project built with:

- `python-telegram-bot` (v20+)
- `SQLite` (auto-created on first run)
- `pandas`

## Features

- Polling mode (no webhook)
- Automatically creates `bot.db` if it doesn't exist
- Save notes with `/add <text>`
- List latest notes with `/list`

## Requirements

- Python 3.10+

## Setup

1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a Telegram bot using [@BotFather](https://t.me/BotFather) and copy the token.

4. Export your token:

```bash
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
```

## Run

```bash
python main.py
```

The bot runs using long polling.

## Commands

- `/start` - Welcome + command help
- `/help` - Command help
- `/add <note text>` - Add a note
- `/list` - Show your latest 10 notes
