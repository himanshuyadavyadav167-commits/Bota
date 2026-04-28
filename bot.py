import sqlite3
import datetime
import random
import string
import threading
import os

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8213230162:AAHoiA3-h1P3cPZYw89ebnEzxP4MnlJvP7Q"
ADMIN_ID = 6676943475
UPI_ID = "himanshuji90million@fam"

# =========================
# FLASK
# =========================
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot Running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, category TEXT, approved INTEGER, code TEXT, ref INTEGER DEFAULT 0, free_entry INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS payments (user_id INTEGER, utr TEXT, date TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS videos (user_id INTEGER, link TEXT, date TEXT)")
conn.commit()

# =========================
# START + REFERRAL
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id

    # referral check
    if context.args:
        ref_id = int(context.args[0])
        if ref_id != uid:
            cur.execute("UPDATE users SET ref = ref + 1 WHERE id=?", (ref_id,))
            conn.commit()

    keyboard = [
        ["🔥 10–500 Followers (₹15)"],
        ["⚡ 500–1000 Followers (₹50)"],
        ["🚀 1000–10000 Followers (₹200)"],
        ["🏆 Leaderboard"]
    ]

    await update.message.reply_text(
        "Welcome!\nChoose category 👇",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# =========================
# CATEGORY + FREE ENTRY
# =========================
async def category(update, context):
    uid = update.message.chat_id
    cat = update.message.text

    cur.execute("SELECT ref, free_entry FROM users WHERE id=?", (uid,))
    data = cur.fetchone()

    refs = data[0] if data else 0
    free = data[1] if data else 0

    fee = "15" if "15" in cat else "50" if "50" in cat else "200"

    # FREE ENTRY LOGIC
    if "15" in cat and refs >= 5 and free == 0:
        cur.execute("UPDATE users SET free_entry=1 WHERE id=?", (uid,))
        conn.commit()

        btn = [[InlineKeyboardButton("📤 Submit UTR", callback_data="submit_pay")]]
        await update.message.reply_text("🎉 Free Entry Unlocked!", reply_markup=InlineKeyboardMarkup(btn))
        return

    btn = [[InlineKeyboardButton("💰 Pay Now", callback_data=f"pay_{fee}")]]
    await update.message.reply_text(f"{cat}\nFee ₹{fee}", reply_markup=InlineKeyboardMarkup(btn))

# =========================
# LEADERBOARD
# =========================
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🏆 Leaderboard\n\n"

    cur.execute("SELECT users.id, users.category, COUNT(videos.user_id) FROM users LEFT JOIN videos ON users.id = videos.user_id GROUP BY users.id ORDER BY COUNT(videos.user_id) DESC LIMIT 10")
    data = cur.fetchall()

    rank = 1
    for d in data:
        msg += f"{rank}. {d[0]} | {d[1]} | Videos: {d[2]}\n"
        rank += 1

    await update.message.reply_text(msg)

# =========================
# PAY
# =========================
async def pay(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text("💳 Pay using UPI 👇")
    await q.message.reply_text(f"💰 `{UPI_ID}`", parse_mode="Markdown")

    btn = [[InlineKeyboardButton("📤 Submit UTR", callback_data="submit_pay")]]
    await q.message.reply_text("After payment click:", reply_markup=InlineKeyboardMarkup(btn))

# =========================
# SUBMIT UTR
# =========================
async def submit_pay(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["mode"] = "utr"
    await q.message.reply_text("Send UTR")

# =========================
# TEXT HANDLER
# =========================
async def text(update, context):
    uid = update.message.chat_id
    msg = update.message.text

    if msg == "🏆 Leaderboard":
        await leaderboard(update, context)
        return

    if msg in ["🔥 10–500 Followers (₹15)", "⚡ 500–1000 Followers (₹50)", "🚀 1000–10000 Followers (₹200)"]:
        await category(update, context)
        return

    # VIDEO
    if msg == "📤 Submit Video":
        context.user_data["mode"] = "video"
        await update.message.reply_text("Send Instagram link")
        return

    if context.user_data.get("mode") == "video":
        today = str(datetime.date.today())

        cur.execute("INSERT INTO videos VALUES (?, ?, ?)", (uid, msg, today))
        conn.commit()

        await update.message.reply_text("✅ Submitted")
        return

    # UTR
    if context.user_data.get("mode") == "utr":
        now = str(datetime.datetime.now())

        cur.execute("INSERT INTO payments VALUES (?, ?, ?)", (uid, msg, now))
        conn.commit()

        await update.message.reply_text("✅ Payment Submitted")

# =========================
# MAIN
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(pay, pattern="pay_"))
app.add_handler(CallbackQueryHandler(submit_pay, pattern="submit_pay"))
app.add_handler(MessageHandler(filters.TEXT, text))

app.run_polling()
