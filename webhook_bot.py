#!/usr/bin/env python3
"""
نسخه Webhook ربات دانلود یوتیوب
مناسب برای استقرار روی Render, Railway, VPS و ...
(مناسب‌تر از polling برای سرورهای ابری)

نکته مهم: این نسخه هنوز برای دانلود ویدیو نیاز به زمان طولانی دارد.
سرورلس خالص (مثل Vercel) همچنان مناسب نیست.
"""

import os
import logging
from flask import Flask, request, jsonify
import telebot
import yt_dlp
import tempfile
import shutil

# ====================== تنظیمات ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # مثلاً: https://your-app.onrender.com

MAX_HEIGHT = 720
COOKIES_FILE = "cookies.txt"
MAX_VIDEO_SIZE_MB = 45

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== توابع دانلود (همان قبلی) ======================
def get_ydl_opts(output_dir: str):
    opts = {
        'format': f'bestvideo[height<={MAX_HEIGHT}]+bestaudio/best[height<={MAX_HEIGHT}]/best',
        'outtmpl': os.path.join(output_dir, '%(title)s [%(id)s].%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    return opts

def find_downloaded_file(directory: str) -> str:
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.webm')):
                return os.path.join(root, file)
    return None

def download_video(url: str) -> tuple:
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            opts = get_ydl_opts(tmpdir)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if 'entries' in info:
                    info = info['entries'][0] if info['entries'] else None
                if not info:
                    return False, "ویدیو پیدا نشد", None

                filepath = find_downloaded_file(tmpdir)
                if not filepath:
                    title = info.get('title', 'video')
                    video_id = info.get('id', '')
                    for ext in ['mp4', 'mkv']:
                        candidate = os.path.join(tmpdir, f"{title} [{video_id}].{ext}")
                        if os.path.exists(candidate):
                            filepath = candidate
                            break

                if not filepath or not os.path.exists(filepath):
                    return False, "فایل پیدا نشد", None

                return True, filepath, info
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False, str(e), None

def send_video(chat_id: int, filepath: str, info: dict):
    title = info.get('title', 'ویدیو')
    duration = info.get('duration', 0)
    filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
    
    caption = f"✅ <b>{title}</b>\n📦 {filesize_mb:.1f} MB"
    
    try:
        with open(filepath, 'rb') as f:
            if filesize_mb <= MAX_VIDEO_SIZE_MB:
                bot.send_video(chat_id, f, caption=caption, duration=duration, supports_streaming=True)
            else:
                bot.send_document(chat_id, f, caption=caption)
        return True
    except Exception as e:
        logger.error(f"Send error: {e}")
        return False

# ====================== هندلرهای تلگرام ======================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام! لینک ویدیو یوتیوب را بفرستید.")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text.strip()
    chat_id = message.chat.id

    if "youtube" not in text and "youtu.be" not in text:
        bot.reply_to(message, "لینک یوتیوب معتبر بفرستید.")
        return

    bot.reply_to(message, "⏳ در حال دانلود... این کار ممکن است ۱ تا ۳ دقیقه طول بکشد.")

    success, result, info = download_video(text)

    if success:
        send_video(chat_id, result, info)
        try:
            os.remove(result)
        except:
            pass
    else:
        bot.send_message(chat_id, f"❌ خطا: {result}")

# ====================== Webhook Routes ======================
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook_handler():
    """این endpoint را تلگرام کال می‌کند"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Bad request', 400

@app.route('/')
def index():
    return "ربات دانلود یوتیوب فعال است (Webhook mode)"

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """برای تنظیم وب‌هوک یک بار اجرا کنید"""
    if not WEBHOOK_URL:
        return "WEBHOOK_URL تنظیم نشده است", 400
    
    webhook_path = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    result = bot.set_webhook(url=webhook_path)
    if result:
        return f"✅ وب‌هوک تنظیم شد: {webhook_path}"
    return "❌ تنظیم وب‌هوک ناموفق بود"

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    bot.delete_webhook()
    return "وب‌هوک حذف شد"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("ربات در حالت Webhook آماده است...")
    app.run(host="0.0.0.0", port=port)
