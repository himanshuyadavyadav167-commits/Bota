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

cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    category TEXT,
    approved INTEGER,
    code TEXT,
    ref_count INTEGER DEFAULT 0,
    free_used INTEGER DEFAULT 0
)""")

cur.execute("CREATE TABLE IF NOT EXISTS payments (user_id INTEGER, utr TEXT, date TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS videos (user_id INTEGER, link TEXT, date TEXT)")

conn.commit()

# =========================
# START + REF TRACK
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id

    # user create
    cur.execute("INSERT OR IGNORE INTO users (id, category, approved, code) VALUES (?, '', 0, '')", (uid,))
    conn.commit()

    # referral logic
    if context.args:
        ref_id = int(context.args[0])
        if ref_id != uid:
            cur.execute("UPDATE users SET ref_count = ref_count + 1 WHERE id=?", (ref_id,))
            conn.commit()

    keyboard = [
        ["🔥 10–500 Followers (₹15)"],
        ["⚡ 500–1000 Followers (₹50)"],
        ["🚀 1000–10000 Followers (₹200)"],
        ["👥 Refer & Earn"]
    ]

    await update.message.reply_text(
        "👋 Welcome!\nChoose option 👇",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# =========================
# REFERRAL BUTTON
# =========================
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id

    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={uid}"

    cur.execute("SELECT ref_count FROM users WHERE id=?", (uid,))
    refs = cur.fetchone()[0]

    msg = f"""👥 Refer & Earn

🔗 Your Link:
{link}

📊 Your Referrals: {refs}/5

🎁 5 referrals = FREE entry (₹15 category)
"""

    await update.message.reply_text(msg)

# =========================
# CATEGORY + FREE ENTRY
# =========================
async def category(update, context):
    uid = update.message.chat_id
    cat = update.message.text

    cur.execute("SELECT ref_count, free_used FROM users WHERE id=?", (uid,))
    data = cur.fetchone()

    refs = data[0]
    free_used = data[1]

    fee = "15" if "15" in cat else "50" if "50" in cat else "200"

    cur.execute("UPDATE users SET category=? WHERE id=?", (cat, uid))
    conn.commit()

    # FREE ENTRY LOGIC
    if "15" in cat and refs >= 5 and free_used == 0:
        cur.execute("UPDATE users SET free_used=1 WHERE id=?", (uid,))
        conn.commit()

        btn = [[InlineKeyboardButton("📤 Submit UTR", callback_data="submit_pay")]]

        await update.message.reply_text(
            "🎉 FREE ENTRY UNLOCKED!\nClick below to continue 👇",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        return

    btn = [[InlineKeyboardButton("💰 Pay Now", callback_data=f"pay_{fee}")]]
    await update.message.reply_text(f"{cat}\nFee ₹{fee}", reply_markup=InlineKeyboardMarkup(btn))

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
    await q.message.reply_text("✍️ Send your UTR number")

# =========================
# TEXT HANDLER
# =========================
async def text(update, context):
    uid = update.message.chat_id
    msg = update.message.text

    if msg == "👥 Refer & Earn":
        await referral(update, context)
        return

    if msg in ["🔥 10–500 Followers (₹15)", "⚡ 500–1000 Followers (₹50)", "🚀 1000–10000 Followers (₹200)"]:
        await category(update, context)
        return

    # UTR SUBMIT
    if context.user_data.get("mode") == "utr":
        now = str(datetime.datetime.now())

        cur.execute("INSERT INTO payments VALUES (?, ?, ?)", (uid, msg, now))
        conn.commit()

        context.user_data.clear()

        # ADMIN APPROVAL BUTTON
        btn = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}")]]

        await context.bot.send_message(
            ADMIN_ID,
            f"💰 New Payment\n\n👤 User: {uid}\n🔢 UTR: {msg}\n⏰ {now}",
            reply_markup=InlineKeyboardMarkup(btn)
        )

        await update.message.reply_text("✅ Payment submitted! Wait for approval ⏳")

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
    await context.bot.send_message(uid, f"🔑 `{code}`", parse_mode="Markdown")
    await context.bot.send_message(uid, "Use this code in caption", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

    await q.edit_message_text("✅ Approved")

# =========================
# MAIN
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(pay, pattern="pay_"))
app.add_handler(CallbackQueryHandler(submit_pay, pattern="submit_pay"))
app.add_handler(CallbackQueryHandler(approve, pattern="approve_"))
app.add_handler(MessageHandler(filters.TEXT, text))

app.run_polling()
