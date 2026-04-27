import sqlite3
import datetime
import random
import string
import threading
import os

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIG 🔧 =================
TOKEN = "8674366499:AAHdxwGcszTt75pD8jgkTSRHLVnBJUf-LYM"
ADMIN_ID = 6676943475
UPI_ID = "himanshuji90million@fam"

# ================= FLASK =================
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# ================= DB =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, category TEXT, approved INTEGER, code TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS payments (user_id INTEGER, utr TEXT, date TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS videos (user_id INTEGER, link TEXT, date TEXT)")

# ================= GLOBAL STATE FIX =================
user_state = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🔥 10–500 Subs (₹15)"],
        ["⚡ 500–1000 Subs (₹50)"],
        ["🚀 1000–10000 Subs (₹200)"]
    ]

    await update.message.reply_text(
        "👋 Welcome!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ================= CATEGORY =================
async def category(update, context):
    uid = update.message.chat_id
    cat = update.message.text

    fee = "15" if "15" in cat else "50" if "50" in cat else "200"

    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 0, '')", (uid, cat))
    conn.commit()

    btn = [[InlineKeyboardButton("💰 Pay Now", callback_data=f"pay_{fee}")]]
    await update.message.reply_text(cat, reply_markup=InlineKeyboardMarkup(btn))

# ================= PAY =================
async def pay(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text(UPI_ID)

    btn = [[InlineKeyboardButton("Submit UTR", callback_data="utr")]]
    await q.message.reply_text("After payment", reply_markup=InlineKeyboardMarkup(btn))

# ================= UTR =================
async def submit_pay(update, context):
    q = update.callback_query
    await q.answer()

    user_state[q.from_user.id] = "UTR"
    await q.message.reply_text("Send UTR")

# ================= TEXT =================
async def text(update, context):
    uid = update.message.chat_id
    msg = update.message.text

    # CATEGORY
    if msg in ["🔥 10–500 Subs (₹15)", "⚡ 500–1000 Subs (₹50)", "🚀 1000–10000 Subs (₹200)"]:
        await category(update, context)
        return

    # UTR FLOW FIX 🔥
    if user_state.get(uid) == "UTR":
        user_state[uid] = None

        now = str(datetime.datetime.now())
        cur.execute("INSERT INTO payments VALUES (?, ?, ?)", (uid, msg, now))
        conn.commit()

        btn = [[InlineKeyboardButton("Approve", callback_data=f"approve_{uid}")]]

        await context.bot.send_message(
            ADMIN_ID,
            f"User: {uid}\nUTR: {msg}",
            reply_markup=InlineKeyboardMarkup(btn)
        )

        await update.message.reply_text("UTR received")
        return

    # VIDEO FLOW FIX 🔥
    if msg == "Submit Video":
        cur.execute("SELECT approved FROM users WHERE id=?", (uid,))
        d = cur.fetchone()

        if not d or d[0] != 1:
            await update.message.reply_text("Not approved yet")
            return

        user_state[uid] = "VIDEO"
        await update.message.reply_text("Send YouTube link")
        return

    if user_state.get(uid) == "VIDEO":
        user_state[uid] = None

        if "youtube" not in msg:
            await update.message.reply_text("Invalid link")
            return

        today = str(datetime.date.today())
        cur.execute("INSERT INTO videos VALUES (?, ?, ?)", (uid, msg, today))
        conn.commit()

        await update.message.reply_text("Video submitted")
        await context.bot.send_message(ADMIN_ID, f"Video {uid}\n{msg}")

# ================= APPROVE =================
async def approve(update, context):
    q = update.callback_query
    await q.answer()

    uid = int(q.data.split("_")[1])

    code = "FreeSpons-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

    cur.execute("UPDATE users SET approved=1, code=? WHERE id=?", (code, uid))
    conn.commit()

    await context.bot.send_message(uid, f"Approved\nCode: {code}")
    await context.bot.send_message(uid, "Submit Video button enabled")

# ================= LIST (FIX) =================
async def list_cmd(update, context):
    if update.message.chat_id != ADMIN_ID:
        return

    cur.execute("SELECT * FROM payments")
    data = cur.fetchall()

    if not data:
        await update.message.reply_text("No Payments")
        return

    for d in data:
        await update.message.reply_text(f"{d[0]} | {d[1]} | {d[2]}")

# ================= DATA (FIX) =================
async def data_cmd(update, context):
    if update.message.chat_id != ADMIN_ID:
        return

    cur.execute("SELECT * FROM videos")
    data = cur.fetchall()

    if not data:
        await update.message.reply_text("No Videos")
        return

    for d in data:
        await update.message.reply_text(f"{d[0]} | {d[1]} | {d[2]}")

# ================= BOT =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_cmd))
app.add_handler(CommandHandler("data", data_cmd))

app.add_handler(CallbackQueryHandler(pay, pattern="pay_"))
app.add_handler(CallbackQueryHandler(submit_pay, pattern="submit_pay"))
app.add_handler(CallbackQueryHandler(approve, pattern="approve_"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

app.run_polling()
