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
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# GROQ — РАБОЧАЯ ИНИЦИАЛИЗАЦИЯ (groq>=0.11.0)
groq_client = Groq(
    api_key=GROQ_API_KEY,
    http_client_kwargs={"proxies": None}  # Отключаем прокси — 100% фикс
)

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
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

# ======== АНІМАЦІЯ ЗАВАНТАЖЕННЯ ========
def start_loading(cid, text="Генерую"):
    msg = bot.send_message(cid, f"{text} [Ship]")
    loading[cid] = msg.message_id
    anim = ["[Ship]", "[Anchor]", "[Wave]", "[Swirl]", "[Tornado]", "[Ship]", "[Sunset]", "[Cruise]"]
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

# ======== МЕНЮ ========
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
    uid = 1474031301
    reg_date = "2025-11-09"
    if cid not in user_data:
        user_data[cid] = {
            "reg_date": reg_date,
            "username": "@Artem1488962",
            "id": uid,
            "questions": [], "media": [], "video": [], "pres": [], "news": [], "answers": []
        }
    bot.send_message(cid,
        f"<b>Капитан @Tem4ik4751 на мостике!</b>\n"
        f"ID: <code>{uid}</code>\n"
        "Бот работает 24/7 — <b>Слава ЗСУ!</b>\n\n"
        "Выбери функцию [Down Arrow]",
        reply_markup=main_menu())

# ======== ПРОФІЛЬ + ІСТОРІЯ ========
@bot.message_handler(func=lambda m: m.text == "Профиль")
def profile(m):
    cid = m.chat.id
    u = user_data[cid]
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
Username: <b>@Artem1488962</b>
Дата: <b>2025-11-09</b>
<b>Статистика:</b>
[Question] Питань: {len(u['questions'])}
Фото: {len(u['media'])}
Відео: {len(u['video'])}
Презентацій: {len(u['pres'])}
Новин: {len(u['news'])}
Відповідей: {len(u['answers'])}
    """.strip(), reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("h_"))
def history(c):
    cid = c.message.chat.id
    t = c.data[2:]
    maps = {"q":"questions", "m":"media", "v":"video", "p":"pres", "n":"news", "a":"answers"}
    items = user_data[cid].get(maps[t], [])[-10:]
    if not items:
        bot.answer_callback_query(c.id, "Пусто!", show_alert=True)
        return
    title = {"q":"Питання", "m":"Фото", "v":"Відео", "p":"Презентації", "n":"Новини", "a":"Відповіді"}[t]
    text = f"<b>{title} (останні 10):</b>\n\n"
    for i, x in enumerate(items, 1):
        text += f"{i}. <code>{x[:50]}{'...' if len(x)>50 else ''}</code>\n"
    bot.send_message(cid, text)

# ======== ГЕНЕРАТОР МЕДІА ========
@bot.message_handler(func=lambda m: m.text == "Генератор Медіа")
def media_menu(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("Фото", "Відео")
    k.row("Назад")
    bot.send_message(m.chat.id, "Выбирай оружие, капитан!", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Відео"])
def ask_prompt(m):
    media_type = "фото" if "Фото" in m.text else "відео"
    example = "ЗСУ на палубе, закат, фотореализм" if "Фото" in m.text else "ЗСУ на палубе, закат, 10 сек"
    bot.send_message(m.chat.id,
        f"Опиши {media_type}:\n"
        f"Пример: «{example}»",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, generate_photo if "Фото" in m.text else generate_video)

def generate_photo(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["media"].append(prompt)
    load = start_loading(cid, "Генерую фото")
    headers = {"Authorization": f"Bearer {KLING_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post("https://api.klingai.com/v1/images/generations",
            headers=headers,
            json={"prompt": prompt + ", photorealistic, 8K, ultra detailed", "n": 1, "size": "1024x1024"}
        ).json()
        img_url = r["data"][0]["url"]
        stop_loading(cid, load.message_id)
        bot.send_photo(cid, img_url, caption=f"[Camera] {prompt}")
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Помилка генерації. Спробуй ще раз.")

def generate_video(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["video"].append(prompt)
    load = start_loading(cid, "Створюю відео")
    headers = {"Authorization": f"Bearer {KLING_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post("https://api.klingai.com/v1/videos/generations",
            headers=headers,
            json={
                "prompt": prompt + ", cinematic, 4K, ultra realistic, smooth motion",
                "negative_prompt": "blurry, low quality, distortion",
                "duration": 10,
                "aspect_ratio": "16:9"
            }
        ).json()
        task_id = r["data"]["task_id"]
        for _ in range(50):
            time.sleep(6)
            status = requests.get(f"https://api.klingai.com/v1/videos/tasks/{task_id}",
                headers=headers).json()
            if status["data"]["status"] == "completed":
                video_url = status["data"]["video_url"]
                stop_loading(cid, load.message_id)
                bot.send_video(cid, video_url, caption=f"[Film] {prompt}")
                return
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Відео ще обробляється, скоро прийде!")
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, f"Помилка: {str(e)[:100]}")

# ======== МОРСЬКІ НОВИНИ ========
@bot.message_handler(func=lambda m: m.text == "Морські новини")
def news(m):
    cid = m.chat.id
    load = start_loading(cid, "Шукаю новини")
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": "3 головні морські новини за 24 год: заголовок, 2 речення, фото, відео YouTube, джерело. Markdown."}],
            max_tokens=1000
        )
        stop_loading(cid, load.message_id)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False)
        user_data[cid]["news"].append(time.strftime("%H:%M"))
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "GROQ тимчасово недоступний. Спробуй за 10 сек.")

# ======== ПРЕЗЕНТАЦІЇ ========
@bot.message_handler(func=lambda m: m.text == "Створити презентацію")
def create_pres(m):
    bot.send_message(m.chat.id, "Тема презентації?\nПриклад: «Перемога ЗСУ на морі»")
    bot.register_next_step_handler(m, gen_pres)

def gen_pres(m):
    cid = m.chat.id
    topic = m.text
    user_data[cid]["pres"].append(topic)
    load = start_loading(cid, "Створюю NatGeo стиль")
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
            if line.strip():
                pdf.multi_cell(0, 7, line)
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        stop_loading(cid, load.message_id)
        bot.send_document(cid, buffer, caption=topic, filename=f"{topic[:50]}.pdf")
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Помилка створення PDF.")

# ======== ВІДПОВІДІ НА ПИТАННЯ ========
@bot.message_handler(func=lambda m: m.text == "Відповіді на питання")
def ask_q(m):
    bot.send_message(m.chat.id, "Задай питання:\nПриклад: «Коли ЗСУ звільнять Крим?»")
    bot.register_next_step_handler(m, answer_q)

def answer_q(m):
    cid = m.chat.id
    q = m.text
    user_data[cid]["questions"].append(q)
    user_data[cid]["answers"].append(q)
    load = start_loading(cid, "Думаю...")
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": f"Відповідь: {q}. 3 абзаци, фото, відео YouTube, 2 джерела."}],
            max_tokens=1200
        )
        stop_loading(cid, load.message_id)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False)
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "GROQ перевантажено. Спробуй за 10 сек.")

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    bot.send_message(m.chat.id, "Головне меню", reply_markup=main_menu())

# ======== WEBHOOK ========
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    return "", 400  # ← ИСПРАВЛЕНО: запятая → пробел + кавычки

# ======== ЗАПУСК ========
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    print("Бот запущено! Слава ЗСУ!")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
