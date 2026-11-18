# Trading Journal Telegram Bot

A Telegram bot for recording trades and reviewing personal trading history.

## Features
- Add open or closed trades
- Record symbol, direction, entry/exit prices, profit/loss and notes
- View the latest 10 trades
- View total trades, open/closed trades, wins, losses, win rate and recorded P/L
- Delete a trade by its ID
- Per-user trade records using Telegram user IDs
- Flask health endpoint for Render

## Run locally
1. Install dependencies: `pip install -r requirements.txt`
2. Set `BOT_TOKEN` to your Telegram bot token.
3. Run: `python main.py`

## Deploy on Render
Create a Web Service from this repository. Render can use the included `render.yaml`.
Set the environment variable `BOT_TOKEN` to your token.

For persistent trade records, attach a Render persistent disk and set `DB_PATH` to a file path on that disk (for example `/var/data/trades.db`).

This bot is a record-keeping tool only. It does not provide trading signals or financial advice.
