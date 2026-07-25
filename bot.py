#!/usr/bin/env python3
"""
ربات تلگرام برای دانلود ویدیوهای یوتیوب
طراحی شده برای بازیابی ویدیوهای شخصی کاربر (کانال مسدود یا غیرقابل دسترسی)
"""

import telebot
import yt_dlp
import os
import tempfile
import shutil
import logging
from datetime import datetime

# ====================== تنظیمات ======================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # <-- اینجا توکن ربات خودت را از @BotFather بگذار

# حداکثر ارتفاع ویدیو (برای جلوگیری از فایل‌های خیلی بزرگ)
MAX_HEIGHT = 720

# پوشه کوکی (اختیاری - برای ویدیوهای خصوصی)
COOKIES_FILE = "cookies.txt"

# حداکثر حجم برای ارسال به عنوان ویدیو (بیشتر از این به عنوان فایل ارسال می‌شود)
MAX_VIDEO_SIZE_MB = 45

# ====================== لاگ ======================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ====================== توابع کمکی ======================
def get_ydl_opts(output_dir: str, cookies_path: str = None):
    """تنظیمات yt-dlp"""
    opts = {
        'format': f'bestvideo[height<={MAX_HEIGHT}]+bestaudio/best[height<={MAX_HEIGHT}]/best',
        'outtmpl': os.path.join(output_dir, '%(title)s [%(id)s].%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,           # فقط یک ویدیو (برای پلی‌لیست بعداً اضافه می‌کنیم)
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }
    
    if cookies_path and os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path
        logger.info("Using cookies.txt for authentication")
    
    return opts


def find_downloaded_file(directory: str) -> str:
    """جستجوی فایل دانلود شده"""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.webm', '.mov')):
                return os.path.join(root, file)
    return None


def download_video(url: str, cookies_path: str = None) -> tuple:
    """
    دانلود ویدیو با yt-dlp
    returns: (success, file_path or error_message, video_info)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            opts = get_ydl_opts(tmpdir, cookies_path)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                logger.info(f"Extracting info for: {url}")
                info = ydl.extract_info(url, download=True)
                
                if 'entries' in info:  # پلی‌لیست
                    info = info['entries'][0] if info['entries'] else None
                
                if not info:
                    return False, "ویدیو پیدا نشد.", None
                
                # پیدا کردن فایل
                filepath = find_downloaded_file(tmpdir)
                
                if not filepath:
                    # تلاش برای پیدا کردن فایل با نام دقیق
                    title = info.get('title', 'video')
                    video_id = info.get('id', '')
                    for ext in ['mp4', 'mkv', 'webm']:
                        candidate = os.path.join(tmpdir, f"{title} [{video_id}].{ext}")
                        if os.path.exists(candidate):
                            filepath = candidate
                            break
                
                if not filepath or not os.path.exists(filepath):
                    return False, "فایل دانلود شده پیدا نشد.", None
                
                # کپی به خارج از tmpdir تا پاک نشود
                final_path = os.path.join(tmpdir, os.path.basename(filepath))
                if filepath != final_path:
                    shutil.copy2(filepath, final_path)
                
                filesize = os.path.getsize(filepath) / (1024 * 1024)
                logger.info(f"Downloaded: {filepath} ({filesize:.1f} MB)")
                
                return True, filepath, info
                
        except yt_dlp.utils.DownloadError as e:
            err = str(e)
            if "Private video" in err or "unavailable" in err.lower():
                return False, "ویدیو خصوصی است. لطفاً cookies.txt را قرار دهید.", None
            if "Video unavailable" in err:
                return False, "ویدیو در دسترس نیست.", None
            return False, f"خطای دانلود: {err}", None
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False, f"خطای ناشناخته: {str(e)}", None


def send_video_to_user(chat_id: int, filepath: str, info: dict, original_msg_id: int = None):
    """ارسال ویدیو به کاربر"""
    title = info.get('title', 'ویدیو شما')
    duration = info.get('duration', 0)
    uploader = info.get('uploader', '')
    
    caption = f"✅ <b>{title}</b>\n"
    if uploader:
        caption += f"📺 {uploader}\n"
    if duration:
        mins = duration // 60
        secs = duration % 60
        caption += f"⏱ {mins}:{secs:02d}\n"
    
    filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
    caption += f"📦 {filesize_mb:.1f} مگابایت"
    
    try:
        with open(filepath, 'rb') as video_file:
            if filesize_mb <= MAX_VIDEO_SIZE_MB:
                # ارسال به عنوان ویدیو (با پیش‌نمایش)
                bot.send_video(
                    chat_id,
                    video_file,
                    caption=caption,
                    duration=duration,
                    supports_streaming=True,
                    reply_to_message_id=original_msg_id
                )
            else:
                # ارسال به عنوان فایل (برای حجم بیشتر)
                bot.send_document(
                    chat_id,
                    video_file,
                    caption=caption,
                    reply_to_message_id=original_msg_id
                )
        return True
    except Exception as e:
        logger.error(f"Send error: {e}")
        # تلاش دوم به عنوان فایل
        try:
            with open(filepath, 'rb') as f:
                bot.send_document(
                    chat_id,
                    f,
                    caption=caption + "\n(ارسال به عنوان فایل)",
                    reply_to_message_id=original_msg_id
                )
            return True
        except Exception as e2:
            bot.send_message(chat_id, f"❌ خطا در ارسال فایل: {str(e2)}")
            return False


# ====================== هندلرها ======================
@bot.message_handler(commands=['start'])
def start_handler(message):
    welcome = """
سلام! 👋

من ربات دانلود ویدیوهای یوتیوب هستم.

<b>نحوه استفاده:</b>
• فقط لینک ویدیو یوتیوب را بفرستید.
• مثلاً: <code>https://www.youtube.com/watch?v=xxxxxxxx</code>

<b>نکات مهم:</b>
• این ربات برای <b>ویدیوهای شخصی خودتان</b> طراحی شده.
• برای ویدیوهای خصوصی، <code>cookies.txt</code> را در پوشه ربات قرار دهید.
• حداکثر کیفیت: ۷۲۰p (برای ارسال راحت‌تر)
• اگر ویدیو خیلی طولانی است، بهتر است با yt-dlp محلی دانلود کنید.

برای راهنمایی بیشتر: /help
"""
    bot.reply_to(message, welcome)


@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = """
📖 <b>راهنمای کامل ربات</b>

<b>دانلود یک ویدیو:</b>
لینک را مستقیم بفرستید.

<b>دانلود ویدیوهای خصوصی:</b>
۱. مرورگر خود را باز کنید و با حساب یوتیوب لاگین شوید.
۲. افزونه «Get cookies.txt LOCALLY» را نصب کنید.
۳. به youtube.com بروید → کوکی‌ها را خروجی بگیرید.
۴. فایل را cookies.txt نامگذاری کنید و در کنار bot.py بگذارید.

<b>دستورات:</b>
/start - شروع
/help - این راهنما
/status - وضعیت ربات

<b>برای ۲۰۰۰ ویدیو:</b>
• یک به یک لینک‌ها را بفرستید.
• یا از اسکریپت bulk_downloader.py استفاده کنید (بهتر برای حجم زیاد).

<b>نکته مهم:</b>
ربات را روی سرور خارج از ایران اجرا کنید (یوتیوب در ایران مسدود است).
"""
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['status'])
def status_handler(message):
    bot.reply_to(message, "✅ ربات فعال است.\n\nدر حال آماده دانلود ویدیوهای شما...")


@bot.message_handler(func=lambda m: True, content_types=['text'])
def text_handler(message):
    text = message.text.strip()
    
    # چک لینک یوتیوب
    if not any(x in text for x in ['youtube.com', 'youtu.be', 'youtube']):
        bot.reply_to(message, "❌ لطفاً یک لینک معتبر یوتیوب بفرستید.\n\nمثال:\nhttps://www.youtube.com/watch?v=...")
        return
    
    # چک توکن
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        bot.reply_to(message, "⚠️ توکن ربات تنظیم نشده است!\n\nلطفاً در فایل bot.py توکن را جایگزین کنید.")
        return
    
    chat_id = message.chat.id
    url = text
    
    # پیام در حال پردازش
    processing_msg = bot.reply_to(message, "⏳ در حال پردازش لینک...\nلطفاً صبر کنید (ممکن است چند دقیقه طول بکشد)")
    
    try:
        # دانلود
        success, result, info = download_video(url, COOKIES_FILE if os.path.exists(COOKIES_FILE) else None)
        
        # حذف پیام پردازش
        try:
            bot.delete_message(chat_id, processing_msg.message_id)
        except:
            pass
        
        if success:
            bot.send_message(chat_id, "📥 دانلود کامل شد! در حال ارسال...")
            sent = send_video_to_user(chat_id, result, info, message.message_id)
            if sent:
                # پاک کردن فایل (اختیاری)
                try:
                    if os.path.exists(result):
                        os.remove(result)
                except:
                    pass
            else:
                bot.send_message(chat_id, "❌ ارسال ناموفق بود.")
        else:
            bot.send_message(chat_id, f"❌ {result}")
            
    except Exception as e:
        try:
            bot.delete_message(chat_id, processing_msg.message_id)
        except:
            pass
        bot.send_message(chat_id, f"❌ خطای کلی: {str(e)}")


@bot.message_handler(content_types=['document'])
def document_handler(message):
    """دریافت فایل کوکی از کاربر"""
    if message.document.file_name and 'cookie' in message.document.file_name.lower():
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            with open(COOKIES_FILE, 'wb') as f:
                f.write(downloaded_file)
            
            bot.reply_to(message, "✅ فایل cookies.txt ذخیره شد!\n\nحالا می‌توانید لینک ویدیوهای خصوصی خود را بفرستید.")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا در ذخیره کوکی: {str(e)}")
    else:
        bot.reply_to(message, "فایل را دریافت کردم. اگر cookies.txt است، نام آن را cookies.txt بگذارید و دوباره بفرستید.")


# ====================== اجرا ======================
if __name__ == "__main__":
    print("🚀 ربات تلگرام دانلود یوتیوب در حال اجرا...")
    print("برای توقف: Ctrl+C")
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️  هشدار: توکن BOT_TOKEN تنظیم نشده است!")
    
    if os.path.exists(COOKIES_FILE):
        print(f"✅ فایل {COOKIES_FILE} پیدا شد (برای ویدیوهای خصوصی)")
    else:
        print(f"ℹ️  فایل {COOKIES_FILE} پیدا نشد. برای ویدیوهای خصوصی نیاز است.")
    
    bot.infinity_polling(skip_pending=True, timeout=60)
