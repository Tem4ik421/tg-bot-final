# -*- coding: utf-8 -*-
import os
import time
import threading
import base64
import requests
import re
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import google.generativeai as genai
from io import BytesIO

# ======== КОНФИГ — ВСЁ ИЗ RENDER SECRETS ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KLING_API_KEY = os.getenv("KLING_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") or "https://tg-bot-final-1.onrender.com"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

user_data = {}
loading = {}

# ======== 24/7 АНТИФРИЗ ========
def keep_alive():
    while True:
        try:
            requests.get(WEBHOOK_HOST, timeout=10)
        except:
            pass
        time.sleep(600)
threading.Thread(target=keep_alive, daemon=True).start()

# ======== КРАСИВЫЙ ПРОГРЕСС-БАР ========
def progress_bar(cid, text):
    msg = bot.send_message(cid, f"{text} 0%")
    for i in range(10, 101, 10):
        time.sleep(0.35)
        bar = "█" * (i//10) + "░" * (10 - i//10)
        bot.edit_message_text(f"{text} {i}% |{bar}|", cid, msg.message_id)
    return msg.message_id

# ======== ГЛАВНОЕ МЕНЮ ========
def main_menu():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.row("Профиль")
    k.row("Генератор Медиа", "Морские новости")
    k.row("Погода для моряков", "Создать презентацию")
    k.row("Ответы на вопросы")
    return k

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(m):
    cid = m.chat.id
    if cid not in user_data:
        user_data[cid] = {
            "reg_date": "2025-11-10",
            "questions": [], "media": [], "video": [], "pres": [], "news": [], "weather": []
        }
    bot.send_message(cid,
        "<b>Добро пожаловать на борт, капитан @Tem4ik4751!</b>\n\n"
        "ID: <code>1474031301</code>  |  Дата: <b>2025-11-10</b>\n"
        "Самый быстрый морской AI-бот в мире\n"
        "• Фото за 2 сек\n"
        "• Видео за 18 сек\n"
        "• Презентации как в National Geographic\n\n"
        "Готов к плаванию?",
        reply_markup=main_menu())

# ======== ПРОФИЛЬ ========
@bot.message_handler(func=lambda m: m.text == "Профиль")
def profile(m):
    cid = m.chat.id
    u = user_data.get(cid, {})
    text = f"""
<b>Твой морской профиль</b>

ID: <code>1474031301</code>
Username: <b>@Tem4ik4751</b>
Дата: <b>2025-11-10</b>

<b>Статистика:</b>
Вопросов: {len(u.get('questions',[]))}
Фото: {len(u.get('media',[]))}
Видео: {len(u.get('video',[]))}
Презентаций: {len(u.get('pres',[]))}
Новостей: {len(u.get('news',[]))}
Погоды: {len(u.get('weather',[]))}
    """.strip()
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Вопросы", callback_data="h_q"),
        types.InlineKeyboardButton("Фото", callback_data="h_m"),
        types.InlineKeyboardButton("Видео", callback_data="h_v"),
        types.InlineKeyboardButton("Презентации", callback_data="h_p"),
        types.InlineKeyboardButton("Новости", callback_data="h_n"),
        types.InlineKeyboardButton("Погода", callback_data="h_w")
    )
    bot.send_message(cid, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("h_"))
def hist(c):
    cid = c.message.chat.id
    t = c.data[2:]
    maps = {"q":"questions","m":"media","v":"video","p":"pres","n":"news","w":"weather"}
    items = user_data.get(cid, {}).get(maps.get(t, ""), [])[-10:]
    if not items:
        bot.answer_callback_query(c.id, "Пусто на борту", show_alert=True)
        return
    title = {"q":"Вопросы","m":"Фото","v":"Видео","p":"Презентации","n":"Новости","w":"Погода"}[t]
    text = f"<b>{title} (последние 10):</b>\n\n" + "\n".join([f"{i+1}. <code>{x}</code>" for i,x in enumerate(items)])
    bot.send_message(cid, text)

# ======== ГЕНЕРАТОР МЕДИА ========
@bot.message_handler(func=lambda m: m.text == "Генератор Медиа")
def media_menu(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("Фото", "Видео")
    k.row("Назад")
    bot.send_message(m.chat.id, "Что создаём, капитан?", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Видео"])
def ask_media(m):
    typ = "фото" if "Фото" in m.text else "видео"
    example = "контейнеровоз в шторме у мыса Горн, фотореализм" if typ == "фото" else "корабль тонет в 4K, 10 секунд"
    bot.send_message(m.chat.id,
        f"Опиши {typ}:\n\nПример: <i>«{example}»</i>\nМожно на русском!",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, gen_photo if "Фото" in m.text else gen_video)

def gen_photo(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["media"].append(prompt)
    mid = progress_bar(cid, "Генерирую фото")
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "black-forest-labs/flux-1-schnell",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1
            }, timeout=60).json()
        img_b64 = r["choices"][0]["message"]["content"]
        bot.delete_message(cid, mid)
        bot.send_photo(cid, BytesIO(base64.b64decode(img_b64)), caption=f"{prompt}")
    except Exception as e:
        bot.delete_message(cid, mid)
        bot.send_message(cid, f"Ошибка: {str(e)}\nПопробуй через 30 сек")

def gen_video(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["video"].append(prompt)
    mid = progress_bar(cid, "Создаю видео 5 сек")
    try:
        r = requests.post("https://api.klingai.com/v1/videos/generations",
            headers={"Authorization": f"Bearer {KLING_API_KEY}"},
            json={"prompt": prompt, "duration": 5, "aspect_ratio": "16:9"},
            timeout=60).json()
        task_id = r["data"]["task_id"]
        for _ in range(25):
            time.sleep(1.8)
            status = requests.get(f"https://api.klingai.com/v1/videos/tasks/{task_id}",
                headers={"Authorization": f"Bearer {KLING_API_KEY}"}).json()
            if status["data"]["status"] == "completed":
                bot.delete_message(cid, mid)
                bot.send_video(cid, status["data"]["video_url"], caption=f"{prompt}\nГотово за 18 сек!")
                return
        bot.edit_message_text("Видео почти готово — жди 15 сек", cid, mid)
    except Exception as e:
        bot.delete_message(cid, mid)
        bot.send_message(cid, f"Kling перегружен\nПопробуй позже")

# ======== МОРСКИЕ НОВОСТИ ========
@bot.message_handler(func=lambda m: m.text == "Морские новости")
def news(m):
    cid = m.chat.id
    load = bot.send_message(cid, "Ищу свежие новости с моря")
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content("""Найди 3 главные морские новости за последние 24 часа.
        Для каждой: заголовок, 2 предложения, фото (прямая ссылка), видео YouTube, источник URL.
        Формат: Markdown""")
        bot.delete_message(cid, load.message_id)
        bot.send_message(cid, resp.text, disable_web_page_preview=False)
        user_data[cid]["news"].append(datetime.now().strftime("%H:%M"))
    except:
        bot.send_message(cid, "Новости временно недоступны")

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    start(m)

# ======== FLASK ========
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    return "ERROR", 400

@app.route("/")
def index():
    return "Морской бот жив — 10.11.2025 19:01", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Бот запущен: {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
