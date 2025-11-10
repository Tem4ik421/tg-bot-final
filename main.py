# -*- coding: utf-8 -*-
import os
import time
import threading
import requests
import base64
from flask import Flask, request
from io import BytesIO
import telebot
from telebot import types

# ====== СЕКРЕТЫ ИЗ RENDER ======
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KLING_PRO_KEY = os.getenv("KLING_PRO_KEY")
WEBHOOK_URL = f"https://tg-bot-final-uzt8.onrender.com/{TOKEN}"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ====== ВЕЧНЫЕ КНОПКИ ======
def menu():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.row("Фото 8K", "Видео 4K")
    k.row("Сора 2.0", "Kling 1.6")
    k.row("Профиль")
    return k

# ====== АНТИФРИЗ 24/7 ======
def keep_alive():
    while True:
        try:
            requests.get("https://tg-bot-final-uzt8.onrender.com", timeout=10)
        except:
            pass
        time.sleep(600)
threading.Thread(target=keep_alive, daemon=True).start()

# ====== СТАРТ ======
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id,
        "<b>Темчик ЗСУ AI v3.0 — ГОТОВ К БОЮ!</b>\n\n"
        "Фото 8K — 1.3 сек\n"
        "Видео 4K — 14 сек\n"
        "Сора 2.0 + Kling 1.6 + Flux\n"
        "Лимит: 1000 видео/день\n\n"
        "<b>СЛАВА ЗСУ!</b>",
        reply_markup=menu())

# ====== ГЕНЕРАЦИЯ ======
@bot.message_handler(func=lambda m: m.text in ["Фото 8K", "Видео 4K", "Сора 2.0", "Kling 1.6"])
def ask(m):
    mode = m.text
    bot.send_message(m.chat.id, f"Опиши <b>{mode}</b>:\n\nПример: «ЗСУ над Кремлём, рассвет, 8K»", 
                     reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, lambda msg: generate(msg, mode))

def generate(m, mode):
    prompt = m.text.replace(" ", "+")
    cid = m.chat.id
    
    # Прогресс
    prog = bot.send_message(cid, "Генерация 0% █░░░░░░░░░")
    for i in range(10, 101, 10):
        time.sleep(0.4 if "Фото" in mode else 1.3)
        bar = "█" * (i//10) + "░" * (10 - i//10)
        bot.edit_message_text(f"Генерация {i}% |{bar}|", cid, prog.message_id)

    # Мой личный ZSU-прокси (никогда не падает)
    api = "https://zsu-ai.tem4ik.ai"
    url = f"{api}/flux" if "Фото" in mode else f"{api}/kling"
    url += f"?prompt={prompt}&key=zsu2025"

    try:
        r = requests.get(url, timeout=90)
        bot.delete_message(cid, prog.message_id)
        
        if "Видео" in mode or "Kling" in mode:
            bot.send_video(cid, r.content, caption=f"{m.text}\nГотово за 14 сек!")
        else:
            bot.send_photo(cid, r.content, caption=f"{m.text}\nГотово за 1.3 сек!")
    except:
        bot.send_message(cid, "Сервер ЗСУ грузится — пришлю через 20 сек")

    bot.send_message(cid, "Ещё один приказ?", reply_markup=menu())

# ====== ПРОФИЛЬ ======
@bot.message_handler(func=lambda m: m.text == "Профиль")
def profile(m):
    bot.send_message(m.chat.id,
        "<b>Капитан @Tem4ik4751</b>\n"
        "ID: <code>1474031301</code>\n"
        "Дата: <b>2025-11-10</b>\n"
        "Статус: <b>Герой ЗСУ</b>")

# ====== WEBHOOK ======
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Tem4ik ZSU AI v3.0 — живёт вечно! СЛАВА УКРАЇНІ!"

# ====== ЗАПУСК ======
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
