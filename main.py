"""
Бот для создания AI-презентаций в PDF.
Версия 36.9 - FINAL FIX: Completely reworked CSS/HTML for a stable, elegant, magazine-style layout.
"""

import os
import re
import logging
import sqlite3
import requests
import html
import base64
import time
import json
from datetime import datetime

# Импорты для Webhooks
from flask import Flask, request 
import telebot
from telebot import types
from weasyprint import HTML 
import google.generativeai as genai
from PIL import Image

# --- 1. ЗАГРУЗКА НАСТРОЕК (Чтение ключей напрямую из окружения Render) ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY')

# Настройки для Webhooks
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST') # URL, который предоставит Render
PORT = int(os.environ.get('PORT', 5000)) # Порт, который предоставит хостинг

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
user_sessions = {}

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro-latest')
else:
    gemini_model = None

# --- 2. БАЗА ДАННЫХ (без изменений) ---
DB_NAME = 'bot_stats.db'
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS user_stats (user_id INTEGER PRIMARY KEY, presentations_count INTEGER DEFAULT 0, questions_count INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS presentations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, topic TEXT, created_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, question_text TEXT, created_at TEXT)')
    conn.commit(); conn.close(); logging.info(f"База данных инициализирована ({DB_NAME}).")

def save_presentation_topic(user_id, topic):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False); c = conn.cursor()
    c.execute("INSERT INTO presentations (user_id, topic, created_at) VALUES (?, ?, ?)", (user_id, topic, datetime.now().isoformat()))
    c.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (user_id,)); c.execute("UPDATE user_stats SET presentations_count = presentations_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()

def save_question_history(user_id, question):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False); c = conn.cursor()
    c.execute("INSERT INTO questions (user_id, question_text, created_at) VALUES (?, ?, ?)", (user_id, question, datetime.now().isoformat()))
    c.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (user_id,)); c.execute("UPDATE user_stats SET questions_count = questions_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()

def get_user_profile_data(user_id):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False); c = conn.cursor()
    c.execute("SELECT presentations_count, questions_count FROM user_stats WHERE user_id = ?", (user_id,))
    stats = c.fetchone(); p_count, q_count = (stats[0], stats[1]) if stats else (0, 0)
    c.execute("SELECT topic FROM presentations WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_id,))
    topics = [row[0] for row in c.fetchall()]
    c.execute("SELECT question_text FROM questions WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_id,))
    questions = [row[0] for row in c.fetchall()]
    conn.close(); return p_count, q_count, topics, questions

init_db()

# --- 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (без изменений) ---
def call_gemini(prompt, is_json=False):
    if not gemini_model: raise ConnectionError("Модель Gemini не инициализирована.")
    mime_type = "application/json" if is_json else "text/plain"
    config_gemini = genai.types.GenerationConfig(response_mime_type=mime_type)
    response = gemini_model.generate_content(prompt, generation_config=config_gemini)
    text = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(text) if is_json else text

def image_to_base64(path):
    try:
        with open(path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
    except: return ""

def find_image_pixabay(query, user_id, fallback_query=None):
    base_queries = [q for q in [query, fallback_query] if q and q.strip()]
    if not base_queries: base_queries.append("minimalist abstract")
    
    artistic_keywords = ["photorealistic", "cinematic lighting", "dramatic", "masterpiece", "professional photography"]
    queries_to_try = [f"{base_queries[0]} {keyword}" for keyword in artistic_keywords]
    queries_to_try.extend(base_queries)

    for q in queries_to_try:
        try:
            params = {'key': PIXABAY_API_KEY, 'q': q, 'image_type': 'photo', 'safesearch': 'true', 'per_page': 5, 'orientation': 'horizontal'}
            res = requests.get("https://pixabay.com/api/", params=params, timeout=15); res.raise_for_status()
            data = res.json().get('hits', [])
            if data:
                img_url = data[0]['largeImageURL']
                img_resp = requests.get(img_url, timeout=15); img_resp.raise_for_status()
                img_path = os.path.abspath(f"temp_img_{user_id}_{int(time.time())}.jpg")
                with open(img_path, 'wb') as f: f.write(img_resp.content)
                return img_path
        except Exception as e: logging.warning(f"Ошибка Pixabay для '{q}': {e}")
    return None

# --- 4. ГЕНЕРАТОР PDF (WeasyPrint) ---
def create_presentation_pdf(user_id, slides_data):
    filename = f'presentation_{user_id}.pdf'
    
    # Мы используем стили, вдохновленные вашими примерами: два столбца, блок с фото, чистые линии.
    html_head = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Презентация</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&family=Playfair+Display:wght@700&display=swap');

            /* PAGE SETUP */
            @page {{ size: A4; margin: 0; }}
            body {{
                margin: 0; padding: 0; background-color: #f8f8f8;
                font-family: 'Roboto', sans-serif; color: #333; line-height: 1.6;
            }}
            .page {{
                width: 210mm; height: 297mm; page-break-after: always;
                padding: 25mm 25mm 15mm;
                box-sizing: border-box; background-color: #ffffff;
                position: relative;
            }}
            .page:last-of-type {{ page-break-after: avoid; }}
            
            /* HEADINGS */
            h1.main-title {{
                font-family: 'Playfair Display', serif;
                font-size: 38pt; font-weight: 700; margin: 0 0 10mm;
                color: #222; text-align: center; letter-spacing: 0.5px;
            }}
            h2.section-title {{
                font-family: 'Playfair Display', serif;
                font-size: 24px; font-weight: 700; margin-top: 0; margin-bottom: 12px;
                color: #2e5cb8; /* Акцентный синий */
                border-bottom: 2px solid #e0e0e0; padding-bottom: 5px;
            }}
            h3.block-title {{
                font-size: 16px; font-weight: 700; margin-top: 0; margin-bottom: 5px;
                color: #333;
            }}
            p.main-text {{
                font-size: 13px; line-height: 1.7; text-align: justify; margin: 0 0 15px 0;
            }}

            /* IMAGE AND INTRO BLOCK */
            .top-area {{
                display: flex; gap: 25px; width: 100%; margin-bottom: 30px;
                align-items: flex-start;
            }}
            .image-portrait {{
                width: 180px; height: 240px; object-fit: cover;
                border-radius: 4px; box-shadow: 0 5px 15px rgba(0,0,0,0.15);
                flex-shrink: 0;
            }}
            .intro-text-content {{ flex-grow: 1; }}

            /* INFO BLOCKS LAYOUT (Magazine Style) */
            .info-blocks-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr; /* Two equal columns */
                gap: 20px;
                width: 100%;
            }}
            .info-block-item {{
                background-color: #f4f7f9; /* Светлый фон для блоков */
                padding: 15px;
                border-left: 4px solid #2e5cb8; /* Акцентная синяя линия */
                border-radius: 4px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }}

            /* FOOTER */
            .footer {{
                position: absolute;
                bottom: 10mm;
                width: calc(100% - 50mm);
                border-top: 1px solid #ddd;
                padding-top: 5px;
                font-size: 10px;
                color: #999;
                text-align: right;
            }}
        </style>
    </head>
    <body>
    """
    
    slides_html = ""
    for i, slide in enumerate(slides_data):
        img_b64 = image_to_base64(slide.get('image_path'))
        
        slide_html = f'<div class="page">'
        
        # 1. TOP AREA (Image and Intro)
        slide_html += '<div class="top-area">'
        
        # Image column
        if img_b64:
            slide_html += f'<img src="data:image/jpeg;base64,{img_b64}" class="image-portrait">'
        
        # Text column
        slide_html += '<div class="intro-text-content">'
        slide_html += f'<h2 class="section-title">{html.escape(slide["title"])}</h2>'
        slide_html += f'<p class="main-text">{html.escape(slide["intro"])}</p>'
        slide_html += '</div></div>' # Close intro-text-content and top-area
        
        # 2. INFO BLOCKS
        if slide.get("info_blocks"):
            
            # Subtitle/Section Title
            columns_title = slide["info_blocks"][0].get("section_title", "Ключевые моменты")
            slide_html += f'<h2 class="section-title">{html.escape(columns_title)}</h2>'
            
            slide_html += '<div class="info-blocks-grid">'
            for block in slide["info_blocks"]:
                slide_html += '<div class="info-block-item">'
                slide_html += f'<h3 class="block-title">{html.escape(block["title"])}</h3>'
                slide_html += f'<p class="main-text">{html.escape(block["text"])}</p>'
                slide_html += '</div>'
            slide_html += '</div>' # Close info-blocks-grid

        # 3. FOOTER
        slide_html += f'<div class="footer">Страница {i + 1}</div>' 
        slide_html += '</div>' # Close page
        slides_html += slide_html

    final_html = html_head + slides_html + "</body></html>"
    
    # --- ИСПОЛЬЗУЕМ WEASYPRINT ---
    HTML(string=final_html).write_pdf(filename)
    
    return filename

# --- 5. ОБРАБОТЧИКИ TELEGRAM (без изменений, скопировать из последнего рабочего кода) ---

# ... (Оставьте все функции Telegram, DB, Gemini, Webhook, start_generation_process без изменений)

def get_main_menu_keyboard():
# ...
@bot.message_handler(commands=['start'])
def handle_start(message):
# ...
@bot.message_handler(func=lambda msg: msg.text == "Профиль 👤")
def handle_profile(message):
# ...
# ... (и так далее, до самого конца файла main.py)
# ...
@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
# ... (обязательно оставьте критическое исправление с 'if message.text in [...]')
# ...
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
# ...

# --- ЗАПУСК БОТА (Webhooks) ---
app = Flask(__name__)

@app.route('/' + TOKEN, methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def webhook():
    WEBHOOK_URL = f'https://{WEBHOOK_HOST}'
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + TOKEN)
    logging.info("Webhook set successfully.")
    return "Bot started!", 200

if __name__ == '__main__':
    logging.info(f"Running locally on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)