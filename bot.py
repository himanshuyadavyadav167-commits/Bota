import sqlite3
import datetime
import random
import string
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8674366499:AAHdxwGcszTt75pD8jgkTSRHLVnBJUf-LYM"
ADMIN_ID = 6676943475
UPI_ID = "himanshuji90million@fam"

# DATABASE
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, category TEXT, approved INTEGER, code TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS payments (user_id INTEGER, utr TEXT, date TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS videos (user_id INTEGER, link TEXT, date TEXT)")

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["10–500 Subs (₹15)"],
        ["500–1000 Subs (₹50)"],
        ["1000–10000 Subs (₹200)"]
    ]
    await update.message.reply_text(
        "🎯 Free Spons Contest\nChoose Category:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ---------------- CATEGORY ----------------
async def handle_category(update, context):
    user_id = update.message.chat_id
    cat = update.message.text

    fee = "15" if "15" in cat else "50" if "50" in cat else "200"

    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 0, '')", (user_id, cat))
    conn.commit()

    keyboard = [[InlineKeyboardButton("💳 Pay Now", callback_data=f"pay_{fee}")]]

    await update.message.reply_text(
        f"{cat}\nEntry Fee: ₹{fee}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- PAY ----------------
async def pay(update, context):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("📤 Submit Payment", callback_data="submit_payment")]]

    await query.message.reply_text("💰 Pay using UPI 👇")
    await query.message.reply_text(UPI_ID)
    await query.message.reply_text("After payment click below", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- SUBMIT PAYMENT ----------------
async def submit_payment(update, context):
    query = update.callback_query
    await query.answer()

    context.user_data["waiting_payment"] = True
    await query.message.reply_text("Send UTR number")

# ---------------- TEXT ----------------
async def text(update, context):
    user_id = update.message.chat_id
    msg = update.message.text

    # CATEGORY
    if msg in ["10–500 Subs (₹15)", "500–1000 Subs (₹50)", "1000–10000 Subs (₹200)"]:
        await handle_category(update, context)
        return

    # VIDEO BUTTON
    if msg == "📤 Submit Video":
        cur.execute("SELECT approved FROM users WHERE id=?", (user_id,))
        data = cur.fetchone()

        if not data or data[0] == 0:
            await update.message.reply_text("❌ Not approved")
            return

        context.user_data["waiting_video"] = True
        await update.message.reply_text("Send YouTube link")
        return

    # VIDEO SUBMIT
    if context.user_data.get("waiting_video"):
        context.user_data["waiting_video"] = False

        if "youtube.com" not in msg and "youtu.be" not in msg:
            await update.message.reply_text("❌ Invalid YouTube link")
            return

        today = str(datetime.date.today())

        cur.execute("SELECT * FROM videos WHERE user_id=? AND date=?", (user_id, today))
        if cur.fetchone():
            await update.message.reply_text("❌ Already submitted today")
            return

        cur.execute("INSERT INTO videos VALUES (?, ?, ?)", (user_id, msg, today))
        conn.commit()

        await update.message.reply_text("✅ Video Submitted")

        await context.bot.send_message(ADMIN_ID, f"Video from {user_id}\n{msg}")
        return

    # PAYMENT
    if context.user_data.get("waiting_payment"):
        context.user_data["waiting_payment"] = False

        now = str(datetime.datetime.now())

        cur.execute("INSERT INTO payments VALUES (?, ?, ?)", (user_id, msg, now))
        conn.commit()

        keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}")]]

        await context.bot.send_message(
            ADMIN_ID,
            f"User: {user_id}\nUTR: {msg}\nTime: {now}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        await update.message.reply_text("Payment sent for approval")
        return

# ---------------- APPROVE ----------------
async def approve(update, context):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    user_id = int(query.data.split("_")[1])

    code = "FreeSpons-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

    cur.execute("UPDATE users SET approved=1, code=? WHERE id=?", (code, user_id))
    conn.commit()

    keyboard = [["📤 Submit Video"]]

    await context.bot.send_message(user_id, "Approved ✅")
    await context.bot.send_message(user_id, "Copy your code below:")
    await context.bot.send_message(user_id, code)
    await context.bot.send_message(user_id, "Use in description", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    await query.edit_message_text("Approved Done")

# ---------------- LIST ----------------
async def list_cmd(update, context):
    if update.message.chat_id != ADMIN_ID:
        return

    cur.execute("SELECT * FROM payments")
    data = cur.fetchall()

    if not data:
        await update.message.reply_text("No payments")
        return

    for d in data:
        keyboard = [[InlineKeyboardButton("Approve", callback_data=f"approve_{d[0]}")]]

        await update.message.reply_text(
            f"User: {d[0]}\nUTR: {d[1]}\nTime: {d[2]}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ---------------- DATA ----------------
async def data_cmd(update, context):
    if update.message.chat_id != ADMIN_ID:
        return

    cur.execute("SELECT videos.user_id, videos.link, videos.date, users.category FROM videos JOIN users ON videos.user_id = users.id")
    data = cur.fetchall()

    if not data:
        await update.message.reply_text("No data")
        return

    msg = ""
    for d in data:
        msg += f"{d[0]} | {d[3]} | {d[2]}\n{d[1]}\n\n"

    await update.message.reply_text(msg)

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_cmd))
app.add_handler(CommandHandler("data", data_cmd))
app.add_handler(CallbackQueryHandler(pay, pattern="pay_"))
app.add_handler(CallbackQueryHandler(submit_payment, pattern="submit_payment"))
app.add_handler(CallbackQueryHandler(approve, pattern="approve_"))
app.add_handler(MessageHandler(filters.TEXT, text))

app.run_polling()
