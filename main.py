import sqlite3
import datetime
import random
import string
import threading
import os

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# =========================
# CONFIG
# =========================
TOKEN = "8674366499:AAHdxwGcszTt75pD8jgkTSRHLVnBJUf-LYM"
ADMIN_ID = 6676943475
UPI_ID = "himanshuji90million@fam"

# =========================
# FLASK (RENDER FIX)
# =========================
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "🤖 Bot is Running Perfectly!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, category TEXT, approved INTEGER, code TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS payments (user_id INTEGER, utr TEXT, date TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS videos (user_id INTEGER, link TEXT, date TEXT)")

# =========================
# START 🚀
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🔥 10–500 Subs (₹15)"],
        ["⚡ 500–1000 Subs (₹50)"],
        ["🚀 1000–10000 Subs (₹200)"]
    ]

    await update.message.reply_text(
        "👋 *Welcome!* Choose your category 👇",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="Markdown"
    )

# =========================
# CATEGORY
# =========================
async def category(update, context):
    uid = update.message.chat_id
    cat = update.message.text

    fee = "15" if "15" in cat else "50" if "50" in cat else "200"

    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 0, '')", (uid, cat))
    conn.commit()

    btn = [[InlineKeyboardButton("💰 Pay Now", callback_data=f"pay_{fee}")]]

    await update.message.reply_text(
        f"📦 *Category:* {cat}\n💵 *Fee:* ₹{fee}",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode="Markdown"
    )

# =========================
# PAY
# =========================
async def pay(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text("💳 Pay UPI below 👇")
    await q.message.reply_text(f"`{UPI_ID}`", parse_mode="Markdown")

    btn = [[InlineKeyboardButton("📤 Submit UTR No.", callback_data="submit_pay")]]

    await q.message.reply_text(
        "After payment, submit your UTR 👇",
        reply_markup=InlineKeyboardMarkup(btn)
    )

# =========================
# SUBMIT UTR
# =========================
async def submit_pay(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["pay"] = True
    await q.message.reply_text("✍️ Send your *UTR Number* now 👇", parse_mode="Markdown")

# =========================
# TEXT HANDLER
# =========================
async def text(update, context):
    uid = update.message.chat_id
    msg = update.message.text

    # CATEGORY SELECT
    if msg in ["🔥 10–500 Subs (₹15)", "⚡ 500–1000 Subs (₹50)", "🚀 1000–10000 Subs (₹200)"]:
        await category(update, context)
        return

    # VIDEO MODE
    if msg == "📤 Submit Video":
        cur.execute("SELECT approved FROM users WHERE id=?", (uid,))
        d = cur.fetchone()

        if not d or d[0] == 0:
            await update.message.reply_text("❌ Not approved yet!")
            return

        context.user_data["video"] = True
        await update.message.reply_text("🎥 Send YouTube video link 👇")
        return

    if context.user_data.get("video"):
        context.user_data["video"] = False

        if "youtube.com" not in msg and "youtu.be" not in msg:
            await update.message.reply_text("❌ Invalid YouTube link")
            return

        today = str(datetime.date.today())

        cur.execute("SELECT * FROM videos WHERE user_id=? AND date=?", (uid, today))
        if cur.fetchone():
            await update.message.reply_text("⚠️ Already submitted today!")
            return

        cur.execute("INSERT INTO videos VALUES (?, ?, ?)", (uid, msg, today))
        conn.commit()

        await update.message.reply_text("✅ Video submitted successfully!")
        await context.bot.send_message(ADMIN_ID, f"🎥 Video:\n👤 {uid}\n🔗 {msg}")
        return

    # PAYMENT UTR
    if context.user_data.get("pay"):
        context.user_data["pay"] = False

        now = str(datetime.datetime.now())

        cur.execute("INSERT INTO payments VALUES (?, ?, ?)", (uid, msg, now))
        conn.commit()

        btn = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}")]]

        await context.bot.send_message(
            ADMIN_ID,
            f"💰 New Payment\n👤 User: {uid}\n🔢 UTR: {msg}\n⏰ {now}",
            reply_markup=InlineKeyboardMarkup(btn)
        )

        await update.message.reply_text("✅ UTR submitted successfully!")

# =========================
# APPROVE
# =========================
async def approve(update, context):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    uid = int(q.data.split("_")[1])

    code = "FreeSpons-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

    cur.execute("UPDATE users SET approved=1, code=? WHERE id=?", (code, uid))
    conn.commit()

    kb = [["📤 Submit Video"]]

    await context.bot.send_message(uid, "🎉 Approved!")
    await context.bot.send_message(uid, f"🔑 Code: `{code}`", parse_mode="Markdown")

    await context.bot.send_message(
        uid,
        "Now submit your YouTube video 🎥",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

    await q.edit_message_text("Approved")

# =========================
# LIST (ADMIN FIXED)
# =========================
async def list_cmd(update, context):
    uid = update.message.chat_id

    if uid != ADMIN_ID:
        await update.message.reply_text("❌ Not admin")
        return

    cur.execute("SELECT * FROM payments")
    data = cur.fetchall()

    if not data:
        await update.message.reply_text("📭 No payments")
        return

    for d in data:
        btn = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{d[0]}")]]

        await update.message.reply_text(
            f"👤 {d[0]}\n🔢 {d[1]}\n⏰ {d[2]}",
            reply_markup=InlineKeyboardMarkup(btn)
        )

# =========================
# DATA (ADMIN FIXED)
# =========================
async def data_cmd(update, context):
    uid = update.message.chat_id

    if uid != ADMIN_ID:
        await update.message.reply_text("❌ Not admin")
        return

    cur.execute("""
        SELECT videos.user_id, videos.link, videos.date, users.category
        FROM videos
        JOIN users ON videos.user_id = users.id
    """)

    data = cur.fetchall()

    if not data:
        await update.message.reply_text("📭 No videos")
        return

    msg = "📊 *Video Data*\n\n"

    for d in data:
        msg += f"👤 {d[0]} | 📦 {d[3]} | 📅 {d[2]}\n🔗 {d[1]}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# =========================
# BOT START
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_cmd))
app.add_handler(CommandHandler("data", data_cmd))

app.add_handler(CallbackQueryHandler(pay, pattern="pay_"))
app.add_handler(CallbackQueryHandler(submit_pay, pattern="submit_pay"))
app.add_handler(CallbackQueryHandler(approve, pattern="approve_"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

app.run_polling()
