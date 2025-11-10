# -*- coding: utf-8 -*-
import os
import time
import threading
import requests
from flask import Flask, request
import telebot
from telebot import types
from fpdf import FPDF
from io import BytesIO
from groq import Groq

# ======== КОНФІГ ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KLING_API_KEY = os.getenv("KLING_API_KEY")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")  # ← Render даёт URL
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)
user_data = {}
loading = {}

# ======== АНТИФРИЗ ========
def keep_alive():
    while True:
        try:
            requests.get(WEBHOOK_HOST, timeout=10)
        except:
            pass
        time.sleep(300)

threading.Thread(target=keep_alive, daemon=True).start()

# ======== АВТО-WEBHOOK ========
def setup_webhook():
    try:
        info = bot.get_webhook_info()
        if info.url != WEBHOOK_URL:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=WEBHOOK_URL)
            print(f"Webhook встановлено: {WEBHOOK_URL}")
        else:
            print(f"Webhook активний: {info.url}")
    except Exception as e:
        print(f"Помилка webhook: {e}")

# ======== АНІМАЦІЯ ========
def start_loading(cid, text="Генерую"):
    msg = bot.send_message(cid, f"{text} ⛵")
    loading[cid] = msg.message_id
    anim = ["⛵", "⚓", "🌊", "🌀", "🌪", "🚢", "🌅", "🛳"]
    def animate():
        for _ in range(60):
            for e in anim:
                try:
                    bot.edit_message_text(f"{text} {e}", cid, msg.message_id)
                    time.sleep(0.6)
                except:
                    break
    threading.Thread(target=animate, daemon=True).start()
    return msg

def stop_loading(cid, mid):
    loading.pop(cid, None)
    try:
        bot.delete_message(cid, mid)
    except:
        pass

# ======== ГЛАВНОЕ МЕНЮ (КНОПКИ НЕ ПРОПАДАЮТ!) ========
def main_menu():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.row("Профиль")
    k.row("Генератор Медіа", "Морські новини")
    k.row("Створити презентацію", "Відповіді на питання")
    return k

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(m):
    cid = m.chat.id
    if cid not in user_data:
        user_data[cid] = {"questions": [], "media": [], "video": [], "pres": [], "news": [], "answers": []}
    bot.send_message(cid,
        "<b>Капитан @Tem4ik4751 на мостике!</b>\n"
        "ID: <code>1474031301</code>\n"
        "Бот працює 24/7 — <b>Слава ЗСУ!</b>\n\n"
        "<b>Обери функцію</b>",
        reply_markup=main_menu())  # ← КНОПКИ ОСТАЮТСЯ!

# ======== ПРОФІЛЬ ========
@bot.message_handler(func=lambda m: m.text == "Профиль")
def profile(m):
    cid = m.chat.id
    u = user_data.get(cid, {})
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Питання", callback_data="h_q"),
        types.InlineKeyboardButton("Фото", callback_data="h_m"),
        types.InlineKeyboardButton("Відео", callback_data="h_v"),
        types.InlineKeyboardButton("Презентації", callback_data="h_p"),
        types.InlineKeyboardButton("Новини", callback_data="h_n"),
        types.InlineKeyboardButton("Відповіді", callback_data="h_a")
    )
    bot.send_message(cid, f"""
<b>Морський профіль</b>
ID: <code>1474031301</code>
<b>Статистика:</b>
❓ Питань: {len(u.get('questions', []))}
Фото: {len(u.get('media', []))}
Відео: {len(u.get('video', []))}
Презентацій: {len(u.get('pres', []))}
Новин: {len(u.get('news', []))}
Відповідей: {len(u.get('answers', []))}
    """.strip(), reply_markup=kb)

# ======== ГЕНЕРАТОР МЕДІА (ФИКС ОШИБКИ KLING) ========
@bot.message_handler(func=lambda m: m.text == "Генератор Медіа")
def media_menu(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("Фото", "Відео")
    k.row("Назад")
    bot.send_message(m.chat.id, "Обери зброю, капітане!", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Відео"])
def ask_prompt(m):
    media_type = "фото" if "Фото" in m.text else "відео"
    example = "ЗСУ на палубе, закат, фотореализм" if "Фото" in m.text else "ЗСУ на палубе, закат, 10 сек"
    bot.send_message(m.chat.id,
        f"Опиши {media_type}:\n"
        f"Приклад: «{example}»",
        reply_markup=types.ReplyKeyboardRemove())  # ← Убираем временно
    bot.register_next_step_handler(m, generate_photo if "Фото" in m.text else generate_video, m.text)

def generate_photo(m, prompt=None):
    cid = m.chat.id
    prompt = prompt or m.text
    user_data.setdefault(cid, {})["media"].append(prompt)
    load = start_loading(cid, "Генерую фото")

    if not KLING_API_KEY:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "KLING API не налаштований.", reply_markup=main_menu())
        return

    headers = {"Authorization": f"Bearer {KLING_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(
            "https://api.klingai.com/v1/images/generations",
            headers=headers,
            json={"prompt": prompt + ", photorealistic, 8K, ultra detailed", "n": 1, "size": "1024x1024"},
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("data"):
            raise ValueError("Порожня відповідь")
        img_url = data["data"][0]["url"]
        stop_loading(cid, load.message_id)
        bot.send_photo(cid, img_url, caption=f"📸 {prompt}", reply_markup=main_menu())  # ← ВОЗВРАЩАЕМ КНОПКИ!
    except requests.exceptions.HTTPError as e:
        stop_loading(cid, load.message_id)
        try:
            error = r.json().get("error", {}).get("message", "Невідома помилка")
        except:
            error = "Сервер не відповідає"
        bot.send_message(cid, f"Помилка Kling: {error}", reply_markup=main_menu())
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Сервер тимчасово недоступний. Спробуй за 30 сек.", reply_markup=main_menu())

def generate_video(m, prompt=None):
    cid = m.chat.id
    prompt = prompt or m.text
    user_data.setdefault(cid, {})["video"].append(prompt)
    load = start_loading(cid, "Створюю відео")

    if not KLING_API_KEY:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "KLING API не налаштований.", reply_markup=main_menu())
        return

    headers = {"Authorization": f"Bearer {KLING_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(
            "https://api.klingai.com/v1/videos/generations",
            headers=headers,
            json={
                "prompt": prompt + ", cinematic, 4K, ultra realistic, smooth motion",
                "negative_prompt": "blurry, low quality, distortion",
                "duration": 10,
                "aspect_ratio": "16:9"
            },
            timeout=60
        )
        r.raise_for_status()
        task_id = r.json()["data"]["task_id"]

        for _ in range(60):
            time.sleep(6)
            status = requests.get(f"https://api.klingai.com/v1/videos/tasks/{task_id}", headers=headers, timeout=60).json()
            if status["data"]["status"] == "completed":
                video_url = status["data"]["video_url"]
                stop_loading(cid, load.message_id)
                bot.send_video(cid, video_url, caption=f"🎬 {prompt}", reply_markup=main_menu())
                return
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Відео обробляється — прийде автоматично!", reply_markup=main_menu())
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Помилка генерації відео.", reply_markup=main_menu())

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    bot.send_message(m.chat.id, "Головне меню", reply_markup=main_menu())

# ======== ОСТАЛЬНЫЕ ФУНКЦИИ (с возвратом кнопок) ========
@bot.message_handler(func=lambda m: m.text == "Морські новини")
def news(m):
    cid = m.chat.id
    load = start_loading(cid, "Шукаю новини")
    if not groq_client:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "GROQ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": "3 головні морські новини за 24 год: заголовок, 2 речення, фото, відео YouTube, джерело. Markdown."}],
            max_tokens=1000
        )
        stop_loading(cid, load.message_id)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "GROQ тимчасово недоступний.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "Створити презентацію")
def create_pres(m):
    bot.send_message(m.chat.id, "Тема презентації?\nПриклад: «Перемога ЗСУ на морі»", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, gen_pres)

def gen_pres(m):
    cid = m.chat.id
    topic = m.text
    user_data.setdefault(cid, {})["pres"].append(topic)
    load = start_loading(cid, "Створюю PDF")
    if not groq_client:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "GROQ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": f"Презентація: {topic}. 5 слайдів: заголовок, 3 пункти, фото-опис, колір фону (hex). Стиль National Geographic."}],
            max_tokens=1500
        )
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, topic, ln=1, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", "", 11)
        for line in completion.choices[0].message.content.split("\n"):
            if line.strip(): pdf.multi_cell(0, 7, line)
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        stop_loading(cid, load.message_id)
        bot.send_document(cid, buffer, caption=topic, filename=f"{topic[:50]}.pdf", reply_markup=main_menu())
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Помилка створення PDF.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "Відповіді на питання")
def ask_q(m):
    bot.send_message(m.chat.id, "Задай питання:\nПриклад: «Коли ЗСУ звільнять Крим?»", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, answer_q)

def answer_q(m):
    cid = m.chat.id
    q = m.text
    user_data.setdefault(cid, {})["questions"].append(q)
    load = start_loading(cid, "Думаю...")
    if not groq_client:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "GROQ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = BOT.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": f"Відповідь: {q}. 3 абзаци, фото, відео YouTube, 2 джерела."}],
            max_tokens=1200
        )
        stop_loading(cid, load.message_id)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "GROQ перевантажено.", reply_markup=main_menu())

# ======== FLASK ========
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    return "", 400

# ======== ЗАПУСК ========
if __name__ == "__main__":
    print("Запуск бота...")
    setup_webhook()
    print("Бот запущено! Слава ЗСУ!")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
