"""
Бот для создания AI-презентаций в PDF.
Версия 37.2 - FINAL FIX: Applied stable Flexbox/Grid layout, improved image search, and added Maritime News.
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
import random 
from datetime import datetime

# Импорты для Webhooks
from flask import Flask, request 
import telebot
from telebot import types
from weasyprint import HTML 
import google.generativeai as genai
from PIL import Image

# --- 1. ЗАГРУЗКА НАСТРОЕК ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY')

# Настройки для Webhooks
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST') 
PORT = int(os.environ.get('PORT', 5000)) 

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

# --- 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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
    
    artistic_keywords = ["professional photography", "concept art", "high quality", "detailed", "artistic illustration"]
    
    queries_to_try = [f"{base_queries[0]} {keyword}" for keyword in artistic_keywords]
    queries_to_try.extend(base_queries)
    queries_to_try.append("minimalist professional abstract background") 

    for q in queries_to_try:
        try:
            params = {'key': PIXABAY_API_KEY, 'q': q, 'image_type': 'photo', 'safesearch': 'true', 'per_page': 10, 'orientation': 'horizontal'}
            res = requests.get("https://pixabay.com/api/", params=params, timeout=15); res.raise_for_status()
            data = res.json().get('hits', [])
            
            if data:
                img_url = random.choice(data)['largeImageURL'] 
                
                img_resp = requests.get(img_url, timeout=15); img_resp.raise_for_status()
                img_path = os.path.abspath(f"temp_img_{user_id}_{int(time.time())}.jpg")
                with open(img_path, 'wb') as f: f.write(img_resp.content)
                return img_path
        except Exception as e: logging.warning(f"Ошибка Pixabay для '{q}': {e}")
    
    return None

def fetch_maritime_news():
    # Заглушка (Mock Data) для демонстрации функционала на Render
    news_data = [
        {"title": "Суецкий канал вводит новые правила для крупнотоннажных судов", "link": "https://example.com/suez-rules", "snippet": "Администрация Суэцкого канала (SCA) объявила об ужесточении требований безопасности и лоцманской проводки...", "source": "MarineLog"},
        {"title": "Рост цен на фрахт судов: обзор отрасли", "link": "https://example.com/freight-prices", "snippet": "Аналитики прогнозируют дальнейший рост тарифов на контейнерные перевозки из-за дефицита мощностей в Азии.", "source": "ShippingToday"},
        {"title": "Новые технологии: Автономные корабли в Балтийском море", "link": "https://example.com/autonomous-ships", "snippet": "Первое полностью автономное грузовое судно успешно завершило тестовый рейс в сложных погодных условиях.", "source": "TechMaritime"}
    ]
    
    output = "⚓ **Актуальные Морские Новости (Заглушка):**\n\n"
    if not news_data:
         return "ℹ️ Извините, не удалось получить актуальные морские новости."

    for i, item in enumerate(news_data):
        output += f"**{i+1}. {item['title']}**\n"
        output += f"_{item['source']}_: {item['snippet'][:80]}...\n"
        output += f"[Подробнее]({item['link']})\n\n"
        
    output += "ℹ️ *Внимание: На Render доступ к внешним поисковым API ограничен. Данные являются демонстрационными.*"
    return output

# --- 4. ГЕНЕРАТОР PDF (WeasyPrint) ---
def create_presentation_pdf(user_id, slides_data):
    filename = f'presentation_{user_id}.pdf'
    
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
                font-size: 24px; font-weight: 700; margin-top: 0; margin-bottom: 15px;
                color: #2e5cb8; /* Акцентный синий */
                border-bottom: 2px solid #2e5cb8; 
                padding-bottom: 5px;
            }}
            h3.block-title {{
                font-size: 16px; font-weight: 700; margin-top: 0; margin-bottom: 5px;
                color: #333;
            }}
            p.main-text {{
                font-size: 13px; line-height: 1.7; text-align: justify; margin: 0 0 15px 0;
            }}

            /* IMAGE AND INTRO BLOCK - УЛУЧШЕННЫЙ FLEXBOX */
            .top-area {{
                display: flex; gap: 25px; width: 100%; margin-bottom: 30px;
                align-items: flex-start;
            }}
            .image-portrait-container {{
                width: 180px; height: 240px; 
                flex-shrink: 0;
                background-color: #eee; 
                display: flex; align-items: center; justify-content: center;
                border-radius: 4px; box-shadow: 0 5px 15px rgba(0,0,0,0.15);
            }}
            .image-portrait {{
                width: 100%; height: 100%; object-fit: cover;
                border-radius: 4px;
            }}
            .intro-text-content {{ flex-grow: 1; }}

            /* INFO BLOCKS LAYOUT - GRID */
            .info-blocks-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr; 
                gap: 20px;
                width: 100%;
            }}
            .info-block-item {{
                background-color: #f4f7f9; 
                border: 1px solid #e0e0e0; 
                padding: 15px;
                border-radius: 4px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }}
            .info-block-item h3 {{
                 color: #2e5cb8; 
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
        
        # Image column: теперь всегда имеет контейнер для сохранения верстки
        slide_html += '<div class="image-portrait-container">'
        if img_b64:
            slide_html += f'<img src="data:image/jpeg;base64,{img_b64}" class="image-portrait">'
        slide_html += '</div>'
        
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

# --- 5. ОБРАБОТЧИКИ TELEGRAM ---

def get_main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(types.KeyboardButton("Создать презентацию 🎨"), 
                 types.KeyboardButton("Maritime News ⚓"),
                 types.KeyboardButton("Ответы на вопросы ❓"), 
                 types.KeyboardButton("Профиль 👤"))
    return keyboard

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_sessions.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "👋 **Привет!**\n\nЯ AI-ассистент для создания стильных PDF-презентаций.", reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')

# НОВЫЙ ОБРАБОТЧИК ДЛЯ НОВОСТЕЙ
@bot.message_handler(func=lambda msg: msg.text == "Maritime News ⚓")
def handle_maritime_news(message):
    chat_id = message.chat.id
    
    last_msg = bot.send_message(chat_id, "⏳ Ищу актуальные морские новости...")
    
    try:
        news_text = fetch_maritime_news()
        bot.edit_message_text(news_text, chat_id, last_msg.message_id, parse_mode='Markdown', disable_web_page_preview=True)
        
    except Exception as e:
        bot.edit_message_text(f"🚫 Произошла ошибка при получении новостей: {e}", chat_id, last_msg.message_id)

@bot.message_handler(func=lambda msg: msg.text == "Профиль 👤")
def handle_profile(message):
    user_id = message.from_user.id
    p_count, q_count, topics, questions = get_user_profile_data(user_id)
    
    topic_list = "\n".join([f"  • *{topic[:35]}...*" for topic in topics]) if topics else "  Нет данных"
    q_list = "\n".join([f"  • *{q[:35]}...*" for q in questions]) if questions else "  Нет данных"

    profile_text = f"""
**Профиль пользователя** 👤
---
**Создано презентаций:** {p_count}
**Задано вопросов:** {q_count}

**Последние темы презентаций:**
{topic_list}

**Последние вопросы:**
{q_list}
    """
    bot.send_message(message.chat.id, profile_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "Ответы на вопросы ❓")
def handle_qna_start(message):
    user_id = message.from_user.id
    user_sessions[user_id] = {'state': 'waiting_qna_question'}
    bot.send_message(message.chat.id, "💬 **Задайте любой вопрос.** Я использую Gemini, чтобы дать точный и развернутый ответ.", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda msg: msg.text == "Создать презентацию 🎨")
def handle_presentation_start(message):
    user_id = message.from_user.id
    user_sessions[user_id] = {'state': 'waiting_topic'}
    bot.send_message(message.chat.id, "✨ **Введите тему презентации.**\n\n_Например: 'Будущее квантовых компьютеров' или 'История римских легионов'._", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    session = user_sessions.get(user_id)

    # --- ИСКЛЮЧЕНИЕ КНОПОК ГЛАВНОГО МЕНЮ ---
    if message.text in ["Создать презентацию 🎨", "Ответы на вопросы ❓", "Профиль 👤", "Maritime News ⚓"]:
        return

    # Решта логіки (для введення тексту теми або питання):
    if not session:
        return handle_start(message)
    
    if session['state'] == 'waiting_topic':
        session['topic'] = message.text
        session['state'] = 'waiting_slide_count'
        
        keyboard = types.InlineKeyboardMarkup(row_width=3)
        keyboard.add(types.InlineKeyboardButton("3 слайда", callback_data='slide_count_3'),
                     types.InlineKeyboardButton("5 слайдов", callback_data='slide_count_5'),
                     types.InlineKeyboardButton("7 слайдов", callback_data='slide_count_7'))
        keyboard.add(types.InlineKeyboardButton("10 слайдов", callback_data='slide_count_10'),
                     types.InlineKeyboardButton("15 слайдов", callback_data='slide_count_15'))
        
        bot.send_message(chat_id, f"Тема: _{session['topic']}_\n\n🔢 **Выберите количество слайдов:**", reply_markup=keyboard, parse_mode='Markdown')

    elif session['state'] == 'waiting_qna_question':
        handle_qna_question(message)
        
    else:
        if session.get('state') != 'generating':
            return handle_start(message)

def is_math_query(text: str):
    return bool(re.search(r'\d[\+\-\*\/]\d', text) or re.search(r'\b(что|как|почему|объясни|зачем)\b', text, re.IGNORECASE))

def handle_qna_question(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not GEMINI_API_KEY or not is_math_query(message.text):
        bot.send_message(chat_id, "Извините, эта функция работает только для сложных вопросов, требующих расчетов или развернутого ответа.")
        user_sessions.pop(user_id, None)
        return bot.send_message(chat_id, "Готов к новым задачам!", reply_markup=get_main_menu_keyboard())

    last_msg = bot.send_message(chat_id, "⏳ Думаю над ответом...")
    save_question_history(user_id, message.text)
    
    try:
        prompt = f"Ответь максимально подробно и четко на вопрос: {message.text}"
        response_text = call_gemini(prompt)
        bot.edit_message_text(f"✅ **Ответ готов:**\n\n{response_text}", chat_id, last_msg.message_id, parse_mode='Markdown')
        
    except ConnectionError:
        bot.edit_message_text("🚫 Ошибка: Ключ Gemini API не установлен.", chat_id, last_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"🚫 Произошла ошибка при получении ответа: {e}", chat_id, last_msg.message_id)
    finally:
        user_sessions.pop(user_id, None)
        bot.send_message(chat_id, "Готов к новым задачам!", reply_markup=get_main_menu_keyboard())

def start_generation_process(user_id, chat_id, slide_count):
    session = user_sessions.get(user_id)
    if not session: return
        
    session['state'] = 'generating'
    last_msg_id = session.get('last_msg_id')
    
    temp_files = []
    pdf_file = None
    try:
        bot.edit_message_text("⏳ Генерирую контент (1/3)...", chat_id, last_msg_id)
        
        prompt = (
            f"Создай контент для презентации в журнальном стиле из {slide_count} слайдов на тему '{session['topic']}'. "
            f"Для КАЖДОГО из {slide_count} слайдов верни JSON-объект с ключами: "
            f"'title' (основной заголовок слайда), "
            f"'intro' (вступительный текст на 2-3 развернутых абзаца), "
            f"'image_query' (запрос для красивого портретного или пейзажного изображения), "
            f"'info_blocks' (массив из 2 или 4 объектов. У первого объекта должен быть ключ 'section_title', например, 'Ключевые принципы'). "
            f"У всех объектов должны быть ключи 'title' и 'text' (текст должен быть подробным, на 3-5 предложений)). "
            f"В итоге верни ОДИН БОЛЬШОЙ JSON-массив, содержащий все {slide_count} объектов."
        )
        
        slides_structure = call_gemini(prompt, is_json=True)
        if not isinstance(slides_structure, list) or not slides_structure:
            raise ValueError("AI вернул некорректную структуру данных.")
        
        save_presentation_topic(user_id, session['topic'])
        slides_data = []
        
        bot.edit_message_text("✅ Контент готов. Ищу красивые фото (2/3)...", chat_id, last_msg_id)
        
        for i, slide_struct in enumerate(slides_structure):
            image_query = slide_struct.get('image_query')
            image_path = find_image_pixabay(image_query, user_id, fallback_query=session['topic'])
            
            slide_struct['image_path'] = image_path
            slides_data.append(slide_struct)
            if image_path: temp_files.append(image_path)

        bot.edit_message_text("✅ Фото найдены. Собираю PDF (3/3)...", chat_id, last_msg_id)
        pdf_file = create_presentation_pdf(user_id, slides_data)
        
        with open(pdf_file, 'rb') as doc:
            bot.send_document(chat_id, doc, caption="Ваша презентация готова!")

    except Exception as e:
        logging.error(f"Ошибка в процессе генерации: {e}")
        bot.send_message(chat_id, f"🚫 Произошла критическая ошибка: {e}")
    finally:
        if pdf_file and os.path.exists(pdf_file): os.remove(pdf_file)
        for f in temp_files:
            if f and os.path.exists(f): os.remove(f)
        user_sessions.pop(user_id, None)
        bot.send_message(chat_id, "Готов к новым задачам!", reply_markup=get_main_menu_keyboard())


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    session = user_sessions.get(user_id)

    if not session or session.get('state') != 'waiting_slide_count':
        bot.answer_callback_query(call.id, "Сессия устарела. Начните сначала.", show_alert=True)
        return handle_start(call.message)

    if call.data.startswith('slide_count_'):
        slide_count = int(call.data.split('_')[2])
        session['slide_count'] = slide_count
        session['last_msg_id'] = message_id
        
        bot.edit_message_reply_markup(chat_id, message_id)
        
        start_generation_process(user_id, chat_id, slide_count)
        
    bot.answer_callback_query(call.id)
    

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