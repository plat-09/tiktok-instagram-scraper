import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
import requests
import json
import time
import re
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
load_dotenv()

# --- Настройки ---
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Лист1")
CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "creds.json")
AUTH_FILE = os.getenv("INSTAGRAM_AUTH_FILE", "auth.json")

# --- Авторизация Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
data = sheet.get_all_values()

# --- Разворачиваем редиректы TikTok ---
def resolve_redirect(url):
    try:
        r = requests.get(url, allow_redirects=True, timeout=10)
        return r.url
    except Exception as e:
        print(f"⚠️ Не удалось развернуть ссылку: {e}")
        return url

# --- Приведение ссылки к каноническому виду ---
def shorten_url(url):
    parsed = urlparse(url)
    if "instagram.com" in parsed.netloc and "/reel/" in parsed.path:
        match = re.search(r"/reel/([a-zA-Z0-9_-]+)", url)
        if match:
            return f"https://www.instagram.com/reel/{match.group(1)}/"
    elif "tiktok.com" in parsed.netloc:
        match = re.search(r"/video/(\d+)", url)
        if match:
            return f"https://www.tiktok.com{parsed.path}"
    return url

# --- Instagram API запрос с cookies ---
def get_instagram_stats(shortcode, cookies):
    url = f"https://i.instagram.com/api/v1/media/shortcode/{shortcode}/info/"

    headers = {
        "User-Agent": "Instagram 155.0.0.37.107",
        "X-IG-App-ID": "936619743392459",
        "Cookie": cookies
    }

    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            item = data["items"][0]
            likes = str(item["like_count"])
            views = str(item.get("play_count", ""))
            comments = str(item["comment_count"])
            return likes, views, comments
        else:
            print(f"❌ Instagram API ошибка {res.status_code}: {res.text}")
            return "", "", ""
    except Exception as e:
        print(f"❌ Instagram API сбой: {e}")
        return "", "", ""

# --- Читаем cookies из auth.json и формируем строку ---
def load_cookie_string():
    try:
        with open(AUTH_FILE, "r") as f:
            raw = json.load(f)
            cookies = raw["cookies"]
            return "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    except Exception as e:
        print(f"❌ Не удалось загрузить auth.json: {e}")
        return ""

cookie_string = load_cookie_string()

# --- Основной парсинг ---
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for row_num, row in enumerate(data[1:], start=2):
        try:
            url = row[0] if len(row) > 0 else ""
            if not url or (len(row) > 9 and row[9]):
                continue

            print(f"\n🔍 Обработка строки {row_num}: {url}")
            url = shorten_url(resolve_redirect(url))

            likes, views, comments = "", "", ""

            # --- TikTok ---
            if "tiktok.com" in url:
                page.goto(url, timeout=60000)
                time.sleep(3)
                html = page.content()

                likes = re.search(r'"diggCount":(\d+)', html)
                views = re.search(r'"playCount":(\d+)', html)
                comments = re.search(r'"commentCount":(\d+)', html)

                likes = likes.group(1) if likes else ""
                views = views.group(1) if views else ""
                comments = comments.group(1) if comments else ""

            # --- Instagram Reels через скрытый API ---
            elif "instagram.com/reel/" in url:
                shortcode_match = re.search(r"/reel/([a-zA-Z0-9_-]+)/", url)
                if shortcode_match:
                    shortcode = shortcode_match.group(1)
                    likes, views, comments = get_instagram_stats(shortcode, cookie_string)
                else:
                    print("⚠️ Не удалось извлечь shortcode из ссылки")

            # --- Запись в таблицу ---
            sheet.update(range_name=f"J{row_num}", values=[[likes]])
            sheet.update(range_name=f"K{row_num}", values=[[views]])
            sheet.update(range_name=f"L{row_num}", values=[[comments]])

            print(f"✅ Готово для строки {row_num}: ❤️ {likes} | 👁 {views} | 💬 {comments}")

        except Exception as e:
            print(f"❌ Ошибка в строке {row_num}: {e}")

    browser.close()