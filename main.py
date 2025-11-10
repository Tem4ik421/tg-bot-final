# -*- coding: utf-8 -*-
import os
import time
import threading
import requests
import json
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
import google.generativeai as genai
from fpdf import FPDF
from io import BytesIO

# ======== КОНФИГ ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KLING_API_KEY = os.getenv("KLING_API_KEY")  # Замени на свой с https://app.klingai.com
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://your-bot.onrender.com")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

user_data = {}
loading = {}

# ======== АНТИФРИЗ ========
def keep_alive():
    while True:
        try: requests.get(WEBHOOK_HOST, timeout=10)
        except: pass
        time.sleep(600)
threading.Thread(target=keep_alive, daemon=True).start()

# ======== АНИМАЦИЯ МОРСКАЯ ========
def start_loading(cid, text="Генерирую"):
    msg = bot.send_message(cid, f"{text} ⛵️")
    loading[cid] = msg.message_id
    anim = ["⛵️", "⚓️", "🌊", "🌀", "🌪", "🚢", "🌅", "🛳", "🌊", "⚓"]
    def animate():
        for _ in range(30):
            for emoji in anim:
                try:
                    bot.edit_message_text(f"{text} {emoji}", cid, msg.message_id)
                    time.sleep(0.8)
                except: pass
    threading.Thread(target=animate, daemon=True).start()
    return msg

def stop_loading(cid, mid):
    if cid in loading:
        loading.pop(cid)
    try: bot.delete_message(cid, mid)
    except: pass

# ======== ГЛАВНОЕ МЕНЮ ========
def main_menu():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.row("👤 Профиль")
    k.row("🖼 Генератор Медиа", "🌊 Морские новости")
    k.row("🎨 Создать презентацию", "❓ Ответы на вопросы")
    return k

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(m):
    cid = m.chat.id
    username = m.from_user.username or "Капитан"
    uid = m.from_user.id
    date = "2025-11-09"

    if cid not in user_data:
        user_data[cid] = {
            "reg_date": date,
            "username": f"@{username}",
            "id": uid,
            "questions": [],
            "media": [],
            "video": [],
            "pres": [],
            "news": [],
            "weather": [],
            "answers": []
        }

    bot.send_message(cid,
        f"<b>⚓️ Добро пожаловать на борт, капитан {user_data[cid]['username']}!</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"📅 Дата: <b>{date}</b>\n\n"
        "🚢 <b>Морской AI-бот нового поколения</b>\n"
        "• Реальные видео (Kling AI)\n"
        "• Погода с волнами\n"
        "• Презентации как в NatGeo\n"
        "• Новости с видео\n\n"
        "Выбери функцию ⬇️",
        reply_markup=main_menu())

# ======== ПРОФИЛЬ ========
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):
    cid = m.chat.id
    u = user_data[cid]
    text = f"""
<b>⚓️ Твой морской профиль</b>
🆔 ID: <code>{u['id']}</code>
👤 Username: <b>{u['username']}</b>
📅 Дата: <b>{u['reg_date']}</b>

<b>📊 Статистика:</b>
❓ Вопросов: {len(u['questions'])}
🖼 Фото: {len(u['media'])}
🎬 Видео: {len(u['video'])}
🎨 Презентаций: {len(u['pres'])}
🌊 Новостей: {len(u['news'])}
🌤 Погоды: {len(u['weather'])}
💬 Ответов: {len(u['answers'])}
    """.strip()

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("❓ Вопросы", callback_data="h_q"),
        types.InlineKeyboardButton("🖼 Фото", callback_data="h_m"),
        types.InlineKeyboardButton("🎬 Видео", callback_data="h_v"),
        types.InlineKeyboardButton("🎨 Презентации", callback_data="h_p"),
        types.InlineKeyboardButton("🌊 Новости", callback_data="h_n"),
        types.InlineKeyboardButton("💬 Ответы", callback_data="h_a")
    )
    bot.send_message(cid, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("h_"))
def history(c):
    cid = c.message.chat.id
    t = c.data[2:]
    maps = {"q":"questions", "m":"media", "v":"video", "p":"pres", "n":"news", "a":"answers"}
    items = user_data[cid].get(maps[t], [])[-10:]
    if not items:
        bot.answer_callback_query(c.id, "Пусто на борту", show_alert=True)
        return
    title = {"q":"Вопросы", "m":"Фото", "v":"Видео", "p":"Презентации", "n":"Новости", "a":"Ответы"}[t]
    text = f"<b>{title} (последние 10):</b>\n\n"
    for i, x in enumerate(items, 1):
        text += f"{i}. <code>{x[:60]}{'...' if len(x)>60 else ''}</code>\n"
    bot.send_message(cid, text)

# ======== ГЕНЕРАТОР МЕДИА ========
@bot.message_handler(func=lambda m: m.text == "🖼 Генератор Медиа")
def media_menu(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("📸 Фото", "🎬 Видео")
    k.row("⬅️ Назад")
    bot.send_message(m.chat.id, "Что создаём, капитан?", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["📸 Фото", "🎬 Видео"])
def ask_prompt(m):
    example_en = "a cat in astronaut suit on Mars, photorealistic" if "Фото" in m.text else "container ship unloading in port, 10 sec"
    example_ru = "кот в скафандре на Марсе, фотореализм" if "Фото" in m.text else "контейнеровоз разгружается в порту, 10 сек"
    bot.send_message(m.chat.id,
        f"Опиши {m.text[2:].lower()}:\n\n"
        f"Пример (EN): <i>«{example_en}»</i>\n"
        f"Пример (RU): <i>«{example_ru}»</i>\n"
        "Можно на русском!",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, generate_photo if "Фото" in m.text else generate_video)

def generate_photo(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["media"].append(prompt)
    load = start_loading(cid, "Генерирую фото")
    try:
        # Используем Kling как fallback для фото
        r = requests.post("https://api.klingai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {KLING_API_KEY}"},
            json={"prompt": prompt, "n": 1, "size": "1024x1024"}
        ).json()
        img_url = r["data"][0]["url"]
        stop_loading(cid, load.message_id)
        bot.send_photo(cid, img_url, caption=f"📸 {prompt}")
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, f"Ошибка: {e}")

def generate_video(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["video"].append(prompt)
    load = start_loading(cid, "Создаю видео")
    try:
        r = requests.post("https://api.klingai.com/v1/videos/generations",
            headers={"Authorization": f"Bearer {KLING_API_KEY}"},
            json={"prompt": prompt, "duration": 10}
        ).json()
        task_id = r["data"]["task_id"]
        for _ in range(40):
            time.sleep(5)
            status = requests.get(f"https://api.klingai.com/v1/videos/tasks/{task_id}",
                headers={"Authorization": f"Bearer {KLING_API_KEY}"}).json()
            if status["data"]["status"] == "completed":
                video_url = status["data"]["video_url"]
                stop_loading(cid, load.message_id)
                bot.send_video(cid, video_url, caption=f"🎬 {prompt}")
                return
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Видео в обработке, скоро пришлю!")
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, f"Ошибка: {e}")

# ======== МОРСКИЕ НОВОСТИ ========
@bot.message_handler(func=lambda m: m.text == "🌊 Морские новости")
def news(m):
    cid = m.chat.id
    load = start_loading(cid, "Ищу новости")
    model = genai.GenerativeModel("gemini-1.5-pro")
    try:
        resp = model.generate_content("""
        Найди 3 главные морские новости за последние 24 часа.
        Для каждой:
        - Заголовок
        - 2 предложения
        - Фото (прямая ссылка .jpg/.png)
        - Видео YouTube (встраиваемое)
        - Источник (URL)
        Формат: Markdown
        """)
        stop_loading(cid, load.message_id)
        bot.send_message(cid, resp.text, disable_web_page_preview=False)
        user_data[cid]["news"].append(datetime.now().strftime("%H:%M"))
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Новости временно недоступны")

# ======== ПРЕЗЕНТАЦИИ (NatGeo стиль) ========
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(m):
    bot.send_message(m.chat.id, "Опиши тему презентации:\nПример: «Эволюция парусных судов»")
    bot.register_next_step_handler(m, generate_presentation)

def generate_presentation(m):
    cid = m.chat.id
    topic = m.text
    user_data[cid]["pres"].append(topic)
    load = start_loading(cid, "Создаю презентацию")
    model = genai.GenerativeModel("gemini-1.5-pro")
    try:
        resp = model.generate_content(f"""
        Создай презентацию на тему: "{topic}"
        5 слайдов, каждый:
        - Заголовок
        - 3 пункта
        - Фото (описание для генерации)
        - Цвет фона (hex)
        Стиль: National Geographic
        """)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"Презентация: {topic}", ln=1, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", "", 12)
        lines = resp.text.split("\n")
        for line in lines:
            if line.strip():
                pdf.multi_cell(0, 8, line)
                pdf.ln(2)
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        stop_loading(cid, load.message_id)
        bot.send_document(cid, buffer, caption=f"🎨 {topic}", filename=f"{topic}.pdf")
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Ошибка генерации PDF")

# ======== ОТВЕТЫ НА ВОПРОСЫ ========
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def ask_question(m):
    bot.send_message(m.chat.id, "Задайте вопрос:\nПример: «Расскажи про будущее судоходства»")
    bot.register_next_step_handler(m, answer_question)

def answer_question(m):
    cid = m.chat.id
    q = m.text
    user_data[cid]["questions"].append(q)
    user_data[cid]["answers"].append(q)
    load = start_loading(cid, "Ищу ответ")
    model = genai.GenerativeModel("gemini-1.5-pro")
    try:
        resp = model.generate_content(f"""
        Ответь на вопрос: "{q}"
        - 3 абзаца
        - Фото (описание)
        - Видео YouTube (встраиваемое)
        - 2 источника (URL)
        """)
        stop_loading(cid, load.message_id)
        bot.send_message(cid, resp.text, disable_web_page_preview=False)
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Не удалось ответить")

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    bot.send_message(m.chat.id, "Главное меню", reply_markup=main_menu())

# ======== FLASK ========
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "main":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    print("Бот запущен!")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
