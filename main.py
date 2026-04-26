import os
import sqlite3
import re
import random
import string
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import validators

# --- CONFIGURATION ---
TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN") # Initialized as requested
ADMIN_ID = 6676943475
UPI_ID = "himanshuji90million@fam"

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    # Payments table
    cursor.execute('''CREATE TABLE IF NOT EXISTS payments 
                      (user_id INTEGER, utr TEXT, category TEXT, fee TEXT, 
                       status TEXT, code TEXT, timestamp TEXT)''')
    # Videos table
    cursor.execute('''CREATE TABLE IF NOT EXISTS videos 
                      (user_id INTEGER, category TEXT, link TEXT, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- STATES ---
CHOOSING_CAT, AWAITING_UTR, AWAITING_VIDEO = range(3)

# --- HELPERS ---
def generate_unique_code():
    chars = string.ascii_uppercase + string.digits
    return f"FreeSpons-{''.join(random.choices(chars, k=5))}"

def is_youtube_url(url):
    pattern = r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
    return re.match(pattern, url) and validators.url(url)

# --- START & CATEGORY FLOW ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("10–500 Subs (₹15)", callback_query_data="cat_15_10-500")],
        [InlineKeyboardButton("500–1000 Subs (₹50)", callback_query_data="cat_50_500-1000")],
        [InlineKeyboardButton("1000–10000 Subs (₹200)", callback_query_data="cat_200_1000-10000")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome! Select your YouTube channel category based on your subscriber count:",
        reply_markup=reply_markup
    )
    return CHOOSING_CAT

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Parse data
    _, fee, subs = query.data.split("_")
    context.user_data['fee'] = fee
    context.user_data['subs'] = subs

    text = f"✅ **Selected Category:** {subs} Subscribers\n💰 **Entry Fee:** ₹{fee}\n\nClick the button below to proceed to payment."
    keyboard = [[InlineKeyboardButton("💳 Pay Now", callback_query_data="pay_now")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def pay_now_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Send UPI separately for easy copying
    await context.bot.send_message(query.message.chat_id, "Copy the UPI ID below to make payment:")
    await context.bot.send_message(query.message.chat_id, f"`{UPI_ID}`", parse_mode="MarkdownV2")
    
    keyboard = [[InlineKeyboardButton("📤 Submit Payment", callback_query_data="ask_utr")]]
    await context.bot.send_message(
        query.message.chat_id,
        "After completing the ₹" + context.user_data.get('fee', '0') + " payment, click the button below to submit your UTR.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def ask_utr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(query.message.chat_id, "Please send your **12-digit UTR number** or a screenshot of the payment.")
    return AWAITING_UTR

async def process_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    utr_text = update.message.text if update.message.text else "Screenshot Attachment"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    fee = context.user_data.get('fee', 'N/A')
    subs = context.user_data.get('subs', 'N/A')

    # Save to database
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?)", 
                   (user_id, utr_text, subs, fee, 'pending', None, timestamp))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Payment details submitted! Please wait for admin approval.")

    # Notify Admin
    admin_kb = [[InlineKeyboardButton("✅ Approve", callback_query_data=f"approve_{user_id}")]]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔔 **New Payment Submission**\n\nUser ID: `{user_id}`\nUTR: {utr_text}\nCat: {subs}\nFee: ₹{fee}\nTime: {timestamp}",
        reply_markup=InlineKeyboardMarkup(admin_kb),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- APPROVAL SYSTEM ---
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return

    user_id = int(query.data.split("_")[1])
    code = generate_unique_code()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE payments SET status='approved', code=? WHERE user_id=? AND status='pending'", (code, user_id))
    conn.commit()
    conn.close()

    await query.edit_message_text(f"✅ Approved User {user_id}")
    
    # Message User
    await context.bot.send_message(user_id, "🎉 Congratulations! Your payment has been approved.")
    await context.bot.send_message(user_id, f"Your unique sponsorship code is:")
    await context.bot.send_message(user_id, f"`{code}`", parse_mode="MarkdownV2")
    
    keyboard = [[InlineKeyboardButton("📹 Submit Video", callback_query_data="start_video_sub")]]
    await context.bot.send_message(
        user_id,
        "Instruction: Paste the code above in your YouTube video description.\nOnce uploaded, click the button below to submit your link.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- VIDEO SUBMISSION ---
async def start_video_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    # Verification check
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM payments WHERE user_id=? AND status='approved'", (user_id,))
    if not cursor.fetchone():
        await query.answer("❌ You are not approved for video submission.", show_alert=True)
        return
    conn.close()

    await query.message.reply_text("Please send your YouTube Video Link:")
    return AWAITING_VIDEO

async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    link = update.message.text
    today = datetime.now().strftime("%Y-%m-%d")

    if not is_youtube_url(link):
        await update.message.reply_text("❌ Error: Please send a valid YouTube URL.")
        return AWAITING_VIDEO

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Check daily limit
    cursor.execute("SELECT * FROM videos WHERE user_id=? AND date=?", (user_id, today))
    if cursor.fetchone():
        await update.message.reply_text("⚠️ Limit reached! You can only submit one video per day.")
        conn.close()
        return ConversationHandler.END

    # Get user category
    cursor.execute("SELECT category FROM payments WHERE user_id=?", (user_id,))
    cat = cursor.fetchone()[0]

    cursor.execute("INSERT INTO videos VALUES (?, ?, ?, ?)", (user_id, cat, link, today))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Video link submitted successfully!")
    await context.bot.send_message(ADMIN_ID, f"📹 **New Video Submission**\nUser: `{user_id}`\nLink: {link}")
    return ConversationHandler.END

# --- ADMIN COMMANDS ---
async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, utr, timestamp FROM payments WHERE status='pending'")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No pending payments.")
        return

    for row in rows:
        kb = [[InlineKeyboardButton("✅ Approve", callback_query_data=f"approve_{row[0]}")]]
        await update.message.reply_text(
            f"👤 User: `{row[0]}`\n📝 UTR: {row[1]}\n⏰ Time: {row[2]}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )

async def admin_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, category, date, link FROM videos")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No video submissions in database.")
        return

    msg = "📊 **All Video Submissions:**\n\n"
    for r in rows:
        msg += f"ID: `{r[0]}` | Cat: {r[1]}\nDate: {r[2]}\nLink: {r[3]}\n\n"
    
    if len(msg) > 4096:
        await update.message.reply_text("Data too large to display. Please check DB file.")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Action cancelled.")
    return ConversationHandler.END

# --- MAIN ---
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_video_sub, pattern="start_video_sub")
        ],
        states={
            CHOOSING_CAT: [CallbackQueryHandler(category_selected, pattern="^cat_")],
            AWAITING_UTR: [MessageHandler(filters.TEXT | filters.PHOTO, process_utr)],
            AWAITING_VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video_link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(pay_now_handler, pattern="pay_now"))
    app.add_handler(CallbackQueryHandler(ask_utr_handler, pattern="ask_utr"))
    app.add_handler(CallbackQueryHandler(approve_user, pattern="^approve_"))
    app.add_handler(CommandHandler("list", admin_list))
    app.add_handler(CommandHandler("data", admin_data))

    print("Bot is live...")
    app.run_polling()

if __name__ == "__main__":
    main()
