#!/usr/bin/env python3
"""
اسکریپت دانلود انبوه ویدیوهای یوتیوب (بهترین گزینه برای ۲۰۰۰ ویدیو)
دانلود تمام ویدیوها به صورت محلی روی سرور

استفاده:
    python bulk_downloader.py "https://www.youtube.com/@yourchannel/videos"
    یا
    python bulk_downloader.py --list urls.txt
"""

import yt_dlp
import os
import sys
import argparse
from datetime import datetime

# ====================== تنظیمات ======================
OUTPUT_DIR = "downloaded_videos"           # پوشه خروجی
MAX_HEIGHT = 720                           # حداکثر کیفیت
COOKIES_FILE = "cookies.txt"               # برای ویدیوهای خصوصی
DOWNLOAD_ARCHIVE = "downloaded.txt"        # برای جلوگیری از دانلود تکراری

def get_ydl_opts(output_path: str):
    opts = {
        'format': f'bestvideo[height<={MAX_HEIGHT}]+bestaudio/best[height<={MAX_HEIGHT}]/best',
        'outtmpl': os.path.join(output_path, '%(playlist_index)s - %(title)s [%(id)s].%(ext)s'),
        'merge_output_format': 'mp4',
        'writeinfojson': True,              # ذخیره اطلاعات ویدیو
        'writedescription': True,
        'writesubtitles': False,
        'download_archive': DOWNLOAD_ARCHIVE,
        'ignoreerrors': True,               # ادامه دادن حتی اگر یک ویدیو خطا داد
        'quiet': False,
        'no_warnings': False,
        'progress_hooks': [progress_hook],
    }
    
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
        print("✅ از cookies.txt برای احراز هویت استفاده می‌شود")
    
    return opts


def progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', 'N/A')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        print(f"\r📥 دانلود: {percent} | سرعت: {speed} | زمان باقی‌مانده: {eta}", end='', flush=True)
    elif d['status'] == 'finished':
        print("\n✅ دانلود کامل شد!")


def download_from_url(url: str):
    """دانلود از یک لینک کانال، پلی‌لیست یا ویدیو"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print(f"🚀 شروع دانلود از: {url}")
    print(f"📁 خروجی: {OUTPUT_DIR}")
    print("=" * 50)
    
    opts = get_ydl_opts(OUTPUT_DIR)
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        print("\n" + "=" * 50)
        print("🎉 دانلود انبوه تمام شد!")
        print(f"ویدیوها در پوشه '{OUTPUT_DIR}' ذخیره شدند.")
        
    except Exception as e:
        print(f"\n❌ خطا: {e}")


def download_from_list(list_file: str):
    """دانلود از فایل متنی حاوی لینک‌ها"""
    if not os.path.exists(list_file):
        print(f"❌ فایل {list_file} پیدا نشد!")
        return
    
    with open(list_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"📋 {len(urls)} لینک پیدا شد.")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    opts = get_ydl_opts(OUTPUT_DIR)
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] دانلود: {url}")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"❌ خطا برای {url}: {e}")
            continue
    
    print("\n🎉 تمام لینک‌ها پردازش شدند.")


def get_all_video_urls(channel_url: str, output_file: str = "video_urls.txt"):
    """استخراج تمام لینک‌های ویدیو از کانال و ذخیره در فایل"""
    print(f"🔍 در حال استخراج لیست ویدیوها از: {channel_url}")
    
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            
            if 'entries' in info:
                entries = info['entries']
            else:
                entries = [info]
            
            urls = []
            for entry in entries:
                if entry and entry.get('url'):
                    video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    urls.append(video_url)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                for url in urls:
                    f.write(url + "\n")
            
            print(f"✅ {len(urls)} لینک ویدیو ذخیره شد در {output_file}")
            print("حالا می‌توانید از این فایل برای دانلود انبوه استفاده کنید:")
            print(f"   python bulk_downloader.py --list {output_file}")
            
    except Exception as e:
        print(f"❌ خطا در استخراج: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="دانلود انبوه ویدیوهای یوتیوب")
    parser.add_argument("url", nargs="?", help="لینک کانال، پلی‌لیست یا ویدیو")
    parser.add_argument("--list", "-l", help="فایل متنی حاوی لینک‌ها (هر خط یک لینک)")
    parser.add_argument("--get-urls", "-g", help="استخراج لیست ویدیوها از کانال و ذخیره در فایل")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="پوشه خروجی")
    
    args = parser.parse_args()
    
    if args.get_urls:
        get_all_video_urls(args.get_urls)
    elif args.list:
        download_from_list(args.list)
    elif args.url:
        download_from_url(args.url)
    else:
        print("نحوه استفاده:")
        print("  python bulk_downloader.py \"https://www.youtube.com/@yourchannel/videos\"")
        print("  python bulk_downloader.py --list video_urls.txt")
        print("  python bulk_downloader.py --get-urls \"https://www.youtube.com/@yourchannel/videos\"")
        print("\nنکته: برای کانال خودتان از لینک /videos یا /playlist استفاده کنید.")