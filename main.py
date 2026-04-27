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
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY,
category TEXT,
approved INTEGER,
code TEXT,
date TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
user_id INTEGER,
utr TEXT,
date TEXT,
status TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS videos (
user_id INTEGER,
link TEXT,
category TEXT,
date TEXT
)
""")

conn.commit()

# =========================
# AUTO CLEAN (7 DAYS)
# =========================
def clean_old_data():
    today = datetime.date.today()
    old = today - datetime.timedelta(days=7)

    cur.execute("DELETE FROM payments WHERE date < ?", (str(old),))
    cur.execute("DELETE FROM videos WHERE date < ?", (str(old),))
    conn.commit()

clean_old_data()

# =========================
# LIMIT SYSTEM (50/DAY)
# =========================
def check_limit(cat):
    today = str(datetime.date.today())
    cur.execute("SELECT COUNT(*) FROM users WHERE category=? AND date=?", (cat, today))
    return cur.fetchone()[0] < 50

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🔥 10–500 Subs (₹15)"],
        ["⚡ 500–1000 Subs (₹50)"],
        ["🚀 1000–10000 Subs (₹200)"]
    ]

    await update.message.reply_text(
        "👋 Welcome!\nChoose category 👇",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# =========================
# CATEGORY
# =========================
async def category(update, context):
    uid = update.message.chat_id
    cat = update.message.text
    today = str(datetime.date.today())

    if not check_limit(cat):
        await update.message.reply_text("❌ Daily limit full (50 users)")
        return

    fee = "15" if "15" in cat else "50" if "50" in cat else "200"

    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 0, '', ?)", (uid, cat, today))
    conn.commit()

    btn = [[InlineKeyboardButton("💰 Pay Now", callback_data=f"pay_{fee}")]]

    await update.message.reply_text(
        f"📦 {cat}\n💵 Fee ₹{fee}",
        reply_markup=InlineKeyboardMarkup(btn)
    )

# =========================
# PAY
# =========================
async def pay(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text("💳 UPI ID:")
    await q.message.reply_text(UPI_ID)

    btn = [[InlineKeyboardButton("📤 Submit UTR No.", callback_data="submit_pay")]]

    await q.message.reply_text("After payment 👇", reply_markup=InlineKeyboardMarkup(btn))

# =========================
# SUBMIT UTR
# =========================
async def submit_pay(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["pay"] = True
    await q.message.reply_text("✍️ Send your UTR number now")

# =========================
# DASHBOARD
# =========================
async def dashboard(update, context):
    if update.message.chat_id != ADMIN_ID:
        return

    keyboard = [
        ["📅 Monday", "📅 Tuesday", "📅 Wednesday"],
        ["📅 Thursday", "📅 Friday", "📅 Saturday"],
        ["📅 Sunday"],
        ["🎥 Videos Report"]
    ]

    await update.message.reply_text(
        "📊 WEEKLY DASHBOARD",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# =========================
# DAY DATA FIXED
# =========================
async def day_data(update, context):
    if update.message.chat_id != ADMIN_ID:
        return

    day = update.message.text.replace("📅 ", "")

    cur.execute("SELECT * FROM payments WHERE date LIKE ?", (f"%{day}%",))
    data = cur.fetchall()

    if not data:
        await update.message.reply_text("No data found")
        return

    msg = f"💰 {day} PAYMENTS\n\n"

    for d in data:
        status = "✅ APPROVED" if d[3] == "approved" else "🟡 PENDING"
        msg += f"👤 {d[0]} | 🔢 {d[1]} | {status}\n"

    await update.message.reply_text(msg)

# =========================
# VIDEO REPORT FIXED
# =========================
async def video_report(update, context):
    if update.message.chat_id != ADMIN_ID:
        return

    cur.execute("SELECT * FROM videos")
    data = cur.fetchall()

    msg = "🎥 VIDEO REPORT\n\n"

    for d in data:
        msg += f"👤 {d[0]} | 📦 {d[2]} | 📅 {d[3]}\n🔗 {d[1]}\n\n"

    await update.message.reply_text(msg)

# =========================
# TEXT HANDLER FIXED UTR FLOW
# =========================
async def text(update, context):
    uid = update.message.chat_id
    msg = update.message.text

    if msg in ["🔥 10–500 Subs (₹15)", "⚡ 500–1000 Subs (₹50)", "🚀 1000–10000 Subs (₹200)"]:
        await category(update, context)
        return

    if context.user_data.get("pay"):
        context.user_data["pay"] = False

        now = str(datetime.datetime.now())

        cur.execute("INSERT INTO payments VALUES (?, ?, ?, 'pending')", (uid, msg, now))
        conn.commit()

        btn = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}")]]

        await context.bot.send_message(
            ADMIN_ID,
            f"💰 Payment\n👤 {uid}\n🔢 {msg}",
            reply_markup=InlineKeyboardMarkup(btn)
        )

        await update.message.reply_text("✅ UTR received")

# =========================
# APPROVE FIXED
# =========================
async def approve(update, context):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    uid = int(q.data.split("_")[1])

    cur.execute("UPDATE payments SET status='approved' WHERE user_id=?", (uid,))
    conn.commit()

    await context.bot.send_message(uid, "🎉 Payment Approved!")

# =========================
# BOT START
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("dashboard", dashboard))

app.add_handler(CommandHandler("list", day_data))
app.add_handler(CommandHandler("data", video_report))

app.add_handler(CallbackQueryHandler(pay, pattern="pay_"))
app.add_handler(CallbackQueryHandler(submit_pay, pattern="submit_pay"))
app.add_handler(CallbackQueryHandler(approve, pattern="approve_"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

app.run_polling()
