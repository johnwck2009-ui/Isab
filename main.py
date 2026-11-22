import os
import sqlite3
import asyncio
import logging
from threading import Thread
from flask import Flask, jsonify
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

DB_PATH = os.getenv("DB_PATH", "trades.db")
SYMBOL, SIDE, ENTRY, EXIT, PNL, NOTES = range(6)

app_web = Flask(__name__)

@app_web.get("/")
@app_web.get("/health")
def health():
    return jsonify(status="ok", service="Trading Journal Bot"), 200

def run_web():
    port = int(os.getenv("PORT", "10000"))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry REAL NOT NULL,
                exit REAL,
                pnl REAL,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

def keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Add Trade"), KeyboardButton("📋 My Trades")],
            [KeyboardButton("📊 Statistics"), KeyboardButton("❓ Help")]
        ],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to this bot!\n\n"
        "❄️ 🌿 💊\n"
        "🍀 💊 🚕\n\n"
        "❄️ 🍁 jon 💊 🍀\n\n"
        "💎 ❄️ Anni 🍁 🌿\n\n"
        "❄️ ☃️ 🌿 🥦 🐴 🚛 🍄 🌈\n\n"
        "Click here to shop now.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("DM to shop")]],
            resize_keyboard=True
        )
    )
    await update.message.reply_text(
        "Tap below to contact the shop:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("DM to shop", url="https://t.me/highplugaus")]]
        )
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📒 Trading Journal Help\n\n"
        "/add - Record a trade\n"
        "/trades - View your latest 10 trades\n"
        "/stats - View your trading statistics\n"
        "/delete ID - Delete one of your trades\n"
        "/cancel - Cancel the current action\n\n"
        "Use the menu buttons too. Your records are private to your Telegram account.",
        reply_markup=keyboard()
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Enter the trading symbol (e.g. BTCUSDT, EURUSD, AAPL):")
    return SYMBOL

async def get_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["symbol"] = update.message.text.strip().upper()[:30]
    await update.message.reply_text("Choose the trade direction: Buy/Long or Sell/Short.")
    return SIDE

async def get_side(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip().lower()
    if value in ("buy", "long", "buy/long"):
        context.user_data["side"] = "Buy/Long"
    elif value in ("sell", "short", "sell/short"):
        context.user_data["side"] = "Sell/Short"
    else:
        await update.message.reply_text("Please enter Buy/Long or Sell/Short.")
        return SIDE
    await update.message.reply_text("Enter your entry price (number only):")
    return ENTRY

async def get_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(",", "").strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid positive entry price.")
        return ENTRY
    context.user_data["entry"] = value
    await update.message.reply_text("Enter exit price, or type OPEN if the trade is still open:")
    return EXIT

async def get_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if value.lower() == "open":
        context.user_data["exit"] = None
        context.user_data["pnl"] = None
        await update.message.reply_text("Add an optional note, or type - to skip:")
        return NOTES
    try:
        exit_price = float(value.replace(",", ""))
        if exit_price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Enter a valid positive exit price, or type OPEN.")
        return EXIT
    context.user_data["exit"] = exit_price
    await update.message.reply_text("Enter profit/loss amount (number; use a minus sign for a loss):")
    return PNL

async def get_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["pnl"] = float(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("Please enter a valid number for profit/loss.")
        return PNL
    await update.message.reply_text("Add an optional note, or type - to skip:")
    return NOTES

async def get_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    if notes == "-":
        notes = ""
    data = context.user_data
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO trades (user_id, symbol, side, entry, exit, pnl, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (update.effective_user.id, data["symbol"], data["side"], data["entry"],
             data.get("exit"), data.get("pnl"), notes[:500])
        )
        trade_id = cur.lastrowid
    context.user_data.clear()
    status = "Open trade" if data.get("exit") is None else "Closed trade"
    await update.message.reply_text(
        f"✅ {status} saved!\nTrade ID: #{trade_id}\n"
        f"{data['symbol']} · {data['side']} · Entry: {data['entry']}",
        reply_markup=keyboard()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Action cancelled.", reply_markup=keyboard())
    return ConversationHandler.END

async def trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (update.effective_user.id,)
        ).fetchall()
    if not rows:
        await update.message.reply_text("You haven't recorded any trades yet. Use /add to begin.", reply_markup=keyboard())
        return
    lines = ["📋 Your latest trades:"]
    for r in rows:
        result = "OPEN" if r["exit"] is None else f"Exit: {r['exit']} | P/L: {r['pnl'] if r['pnl'] is not None else '—'}"
        lines.append(f"\n#{r['id']} {r['symbol']} · {r['side']}\nEntry: {r['entry']} · {result}")
        if r["notes"]:
            lines.append(f"Note: {r['notes']}")
    await update.message.reply_text("\n".join(lines), reply_markup=keyboard())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN exit IS NULL THEN 1 ELSE 0 END) AS opened,
                   SUM(CASE WHEN exit IS NOT NULL THEN 1 ELSE 0 END) AS closed,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE WHEN exit IS NOT NULL THEN COALESCE(pnl, 0) ELSE 0 END) AS total_pnl
            FROM trades WHERE user_id=?
        """, (update.effective_user.id,)).fetchone()
    total = row["total"] or 0
    closed = row["closed"] or 0
    wins = row["wins"] or 0
    losses = row["losses"] or 0
    win_rate = (wins / closed * 100) if closed else 0
    await update.message.reply_text(
        "📊 Your Trading Statistics\n\n"
        f"Total trades: {total}\nOpen trades: {row['opened'] or 0}\n"
        f"Closed trades: {closed}\nWins: {wins}\nLosses: {losses}\n"
        f"Win rate: {win_rate:.1f}%\n"
        f"Recorded P/L: {row['total_pnl'] or 0:.2f}",
        reply_markup=keyboard()
    )

async def delete_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delete ID (example: /delete 12)")
        return
    try:
        trade_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Trade ID must be a number.")
        return
    with db() as conn:
        cur = conn.execute("DELETE FROM trades WHERE id=? AND user_id=?", (trade_id, update.effective_user.id))
    if cur.rowcount:
        await update.message.reply_text(f"🗑 Trade #{trade_id} deleted.", reply_markup=keyboard())
    else:
        await update.message.reply_text("Trade not found in your records.", reply_markup=keyboard())

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "➕ Add Trade":
        return await add_start(update, context)
    if text == "📋 My Trades":
        return await trades(update, context)
    if text == "📊 Statistics":
        return await stats(update, context)
    if text == "❓ Help":
        return await help_command(update, context)
    return None

def main():
    init_db()
    Thread(target=run_web, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start), MessageHandler(filters.Regex("^➕ Add Trade$"), add_start)],
        states={
            SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_symbol)],
            SIDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_side)],
            ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_entry)],
            EXIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_exit)],
            PNL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pnl)],
            NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    application.add_handler(conversation)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("trades", trades))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("delete", delete_trade))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router))
    try:
        application.run_polling(drop_pending_updates=True)
    finally:
        if not loop.is_closed():
            loop.close()

if __name__ == "__main__":
    main()
