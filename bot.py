import sqlite3
import datetime
import requests
import os
import threading

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# =========================
# CONFIG
# =========================
TOKEN = "8213230162:AAHoiA3-h1P3cPZYw89ebnEzxP4MnlJvP7Q"
YOUTUBE_API_KEY = "AIzaSyBs0ilXb61cEjmWAHAiA5pH51h8i5xUDI0"

# =========================
# FLASK (Render fix)
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
conn = sqlite3.connect("demo.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    link TEXT,
    views INTEGER,
    likes INTEGER,
    score INTEGER
)
""")
conn.commit()

# =========================
# YOUTUBE FUNCTIONS
# =========================
def get_video_id(link):
    if "youtu.be" in link:
        return link.split("/")[-1]
    if "v=" in link:
        return link.split("v=")[1].split("&")[0]
    return None

def get_stats(video_id):
    url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={video_id}&key={YOUTUBE_API_KEY}"
    data = requests.get(url).json()

    if not data.get("items"):
        return None, None

    stats = data["items"][0]["statistics"]
    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))

    return views, likes

def calc_score(v, l):
    return v + (l * 2)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        ["📤 Submit Video"],
        ["🏆 Leaderboard"],
        ["🔄 Refresh Ranking"]
    ]
    await update.message.reply_text("Demo Bot 👇", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# =========================
# SUBMIT
# =========================
async def text(update, context):
    msg = update.message.text
    uid = update.message.chat_id

    if msg == "📤 Submit Video":
        context.user_data["mode"] = "submit"
        await update.message.reply_text("Send YouTube link")
        return

    if msg == "🏆 Leaderboard":
        await show_leaderboard(update)
        return

    if msg == "🔄 Refresh Ranking":
        await refresh_all(update)
        return

    # submit link
    if context.user_data.get("mode") == "submit":
        vid = get_video_id(msg)

        if not vid:
            await update.message.reply_text("❌ Invalid link")
            return

        views, likes = get_stats(vid)

        if views is None:
            await update.message.reply_text("❌ API error")
            return

        score = calc_score(views, likes)

        cur.execute("INSERT INTO videos (user_id, link, views, likes, score) VALUES (?, ?, ?, ?, ?)",
                    (uid, msg, views, likes, score))
        conn.commit()

        context.user_data.clear()

        await update.message.reply_text(f"✅ Added\n👁 {views}\n👍 {likes}\n🏆 {score}")

# =========================
# LEADERBOARD
# =========================
async def show_leaderboard(update):
    cur.execute("SELECT link, score FROM videos ORDER BY score DESC LIMIT 10")
    data = cur.fetchall()

    if not data:
        await update.message.reply_text("No data")
        return

    text = "🏆 Leaderboard:\n\n"
    for i, d in enumerate(data, start=1):
        text += f"{i}. {d[1]}\n{d[0]}\n\n"

    await update.message.reply_text(text)

# =========================
# REFRESH ALL DATA
# =========================
async def refresh_all(update):
    cur.execute("SELECT id, link FROM videos")
    rows = cur.fetchall()

    for r in rows:
        vid = get_video_id(r[1])
        views, likes = get_stats(vid)

        if views is None:
            continue

        score = calc_score(views, likes)

        cur.execute("UPDATE videos SET views=?, likes=?, score=? WHERE id=?",
                    (views, likes, score, r[0]))

    conn.commit()

    await update.message.reply_text("🔄 All videos updated!\nNow check leaderboard")

# =========================
# MAIN
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, text))

app.run_polling()
