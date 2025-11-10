# -*- coding: utf-8 -*-
import os
import time
import threading
import base64
import requests
from flask import Flask, request
import telebot
from telebot import types
from io import BytesIO

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KLING_API_KEY = os.getenv("KLING_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") or "https://tg-bot-final-uzt8.onrender.com"
WEBHOOK_URL = f"{WEBHOOK_HOST}/{TOKEN}"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ======== ВЕЧНЫЕ КНОПКИ ========
def eternal_menu():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.row("Профиль", "Генератор Медиа")
    k.row("Морские новости", "Погода для моряков")
    k.row("Создать презентацию", "Ответы на вопросы")
    return k

# ======== 24/7 ========
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
        time.sleep(0.3)
        bar = "█" * (i//10) + "░" * (10 - i//10)
        try: bot.edit_message_text(f"{text} {i}% |{bar}|", cid, msg.message_id)
        except: pass
    return msg.message_id

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id,
        "<b>Капитан @Tem4ik4751 на мостике!</b>\n\n"
        "ID: <code>1474031301</code>\n"
        "Фото за 2 сек • Видео за 18 сек\n"
        "Бот работает 24/7 — Слава ЗСУ!",
        reply_markup=eternal_menu())

# ======== ГЕНЕРАТОР МЕДИА ========
@bot.message_handler(func=lambda m: m.text == "Генератор Медиа")
def media(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("Фото", "Видео")
    k.row("Назад")
    bot.send_message(m.chat.id, "Выбирай оружие, капитан!", reply_markup=k)

@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    bot.send_message(m.chat.id, "На мостике!", reply_markup=eternal_menu())

@bot.message_handler(func=lambda m: m.text in ["Фото", "Видео"])
def ask_prompt(m):
    example = "ЗСУ на палубе, закат, фотореализм" if "Фото" in m.text else "Sea Baby взрывает орков, 8 сек"
    bot.send_message(m.chat.id,
        f"Опиши {m.text.lower()}:\n\nПример: <i>«{example}»</i>",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, gen_photo if "Фото" in m.text else gen_video)

def gen_photo(m):
    prompt = m.text
    mid = progress_bar(m.chat.id, "Фото")
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": "black-forest-labs/flux-1-schnell", "messages": [{"role": "user", "content": prompt}]},
            timeout=60).json()
        if "choices" not in r or not r["choices"]:
            raise Exception("GROQ спит")
        img_b64 = r["choices"][0]["message"]["content"]
        bot.delete_message(m.chat.id, mid)
        bot.send_photo(m.chat.id, BytesIO(base64.b64decode(img_b64)), caption=f"{prompt}")
    except Exception as e:
        bot.delete_message(m.chat.id, mid)
        bot.send_message(m.chat.id, "GROQ перегружен\nПопробуй через 20 сек")
    finally:
        bot.send_message(m.chat.id, "Готов к новому приказу!", reply_markup=eternal_menu())

def gen_video(m):
    prompt = m.text
    mid = progress_bar(m.chat.id, "Видео 5 сек")
    try:
        r = requests.post("https://api.klingai.com/v1/videos/generations",
            headers={"Authorization": f"Bearer {KLING_API_KEY}"},
            json={"prompt": prompt, "duration": 5}, timeout=60).json()
        task_id = r["data"]["task_id"]
        for _ in range(30):
            time.sleep(2)
            status = requests.get(f"https://api.klingai.com/v1/videos/tasks/{task_id}",
                headers={"Authorization": f"Bearer {KLING_API_KEY}"}).json()
            if status["data"]["status"] == "completed":
                bot.delete_message(m.chat.id, mid)
                bot.send_video(m.chat.id, status["data"]["video_url"], caption=f"{prompt}\nГотово!")
                bot.send_message(m.chat.id, "Ещё одно?", reply_markup=eternal_menu())
                return
        bot.edit_message_text("Видео в очереди — жду 20 сек", m.chat.id, mid)
    except:
        bot.send_message(m.chat.id, "Kling устал\nЧерез 5 минут будет готов")
    finally:
        bot.send_message(m.chat.id, "На мостике!", reply_markup=eternal_menu())

# ======== ОСТАЛЬНЫЕ КНОПКИ (просто возвращают меню) ========
@bot.message_handler(func=lambda m: m.text in ["Профиль", "Морские новости", "Погода для моряков", "Создать презентацию", "Ответы на вопросы"])
def stub(m):
    bot.send_message(m.chat.id, "Эта функция в разработке — скоро будет!\nПока генерируй фото/видео!", reply_markup=eternal_menu())

# ======== WEBHOOK ========
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Tem4ikPreSenT живёт 24/7 — 10.11.2025 19:25"

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
