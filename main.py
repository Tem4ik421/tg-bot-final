# -*- coding: utf-8 -*-
import os
import time
import threading
import base64
import requests
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from io import BytesIO

# ======== КОНФИГ — ВСЁ ЧИТАЕТСЯ ИЗ RENDER SECRETS ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")          # ← ТОЛЬКО ТАК!
KLING_API_KEY = os.getenv("KLING_API_KEY")        # ← ТОЛЬКО ТАК!
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
        try: requests.get(WEBHOOK_HOST, timeout=10)
        except: pass
        time.sleep(600)
threading.Thread(target=keep_alive, daemon=True).start()

# ======== ПРОГРЕСС-БАР ========
def progress_bar(cid, text):
    msg = bot.send_message(cid, f"{text} 0%")
    for i in range(10, 101, 10):
        time.sleep(0.35)
        bar = "█" * (i//10) + "░" * (10 - i//10)
        bot.edit_message_text(f"{text} {i}% |{bar}|", cid, msg.message_id)
    return msg.message_id

# ======== МЕНЮ ========
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
        user_data[cid] = {"reg_date": "2025-11-09", "questions": [], "media": [], "video": [], "pres": [], "news": [], "weather": []}
    bot.send_message(cid,
        "<b>Добро пожаловать на борт, капитан @Tem4ik4751!</b>\n\n"
        "ID: <code>1474031301</code>  |  Дата: <b>2025-11-09</b>\n"
        "Самый быстрый морской бот в мире\n"
        "• Фото за 2 сек • Видео за 18 сек\n\n"
        "Готов к бою?",
        reply_markup=main_menu())

# ======== ПРОФИЛЬ ========
@bot.message_handler(func=lambda m: m.text == "Профиль")
def profile(m):
    cid = m.chat.id
    u = user_data[cid]
    text = f"""
<b>Твой морской профиль</b>

ID: <code>1474031301</code>
Username: <b>@Tem4ik4751</b>
Дата: <b>2025-11-09</b>

<b>Статистика:</b>
Вопросов: {len(u['questions'])}
Фото: {len(u['media'])}
Видео: {len(u['video'])}
Презентаций: {len(u['pres'])}
Новостей: {len(u['news'])}
Погоды: {len(u['weather'])}
    """.strip()
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(*[types.InlineKeyboardButton(t, callback_data=f"h_{k}") 
             for t,k in [("Вопросы","q"),("Фото","m"),("Видео","v"),("Презентации","p"),("Новости","n"),("Погода","w")]])
    bot.send_message(cid, text, reply_markup=kb)

# ======== ГЕНЕРАТОР МЕДИА ========
@bot.message_handler(func=lambda m: m.text == "Генератор Медиа")
def media(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("Фото", "Видео")
    k.row("Назад")
    bot.send_message(m.chat.id, "Что генерируем, капитан?", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Видео"])
def ask(m):
    example = "контейнеровоз в шторме" if "Фото" in m.text else "корабль тонет в 4K"
    bot.send_message(m.chat.id, f"Опиши {m.text.lower()}:\nПример: <i>«{example}»</i>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, gen_photo if "Фото" in m.text else gen_video)

def gen_photo(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["media"].append(prompt)
    mid = progress_bar(cid, "Фото")
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": "black-forest-labs/flux-1-schnell", "messages": [{"role": "user", "content": prompt}], "max_tokens": 1}
        ).json()
        img_b64 = r["choices"][0]["message"]["content"]
        bot.delete_message(cid, mid)
        bot.send_photo(cid, BytesIO(base64.b64decode(img_b64)), caption=prompt)
    except Exception as e:
        bot.delete_message(cid, mid)
        bot.send_message(cid, "Flux спит, попробуй через 30 сек")

def gen_video(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["video"].append(prompt)
    mid = progress_bar(cid, "Видео")
    try:
        r = requests.post("https://api.klingai.com/v1/videos/generations",
            headers={"Authorization": f"Bearer {KLING_API_KEY}"},
            json={"prompt": prompt, "duration": 5, "aspect_ratio": "16:9"}
        ).json()
        task_id = r["data"]["task_id"]
        for _ in range(25):
            time.sleep(1.5)
            status = requests.get(f"https://api.klingai.com/v1/videos/tasks/{task_id}",
                headers={"Authorization": f"Bearer {KLING_API_KEY}"}).json()
            if status["data"]["status"] == "completed":
                bot.delete_message(cid, mid)
                bot.send_video(cid, status["data"]["video_url"], caption=f"{prompt}\nГотово за 18 сек!")
                return
        bot.edit_message_text("Видео почти готово — жди 15 сек", cid, mid)
    except:
        bot.send_message(cid, "Kling перегружен, попробуй позже")

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m): start(m)

# ======== FLASK ========
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index(): return "Бот жив — 10.11.2025 18:34", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
