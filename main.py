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

# ======== КОНФІГ ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KLING_API_KEY = os.getenv("KLING_API_KEY")
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

# ======== АНІМАЦІЯ МОРСЬКА ========
def start_loading(cid, text="Генерую"):
    msg = bot.send_message(cid, f"{text} ⛵️")
    loading[cid] = msg.message_id
    anim = ["⛵", "⚓", "🌊", "🌀", "🌪", "🚢", "🌅", "🛳", "🌊", "⚓"]
    def animate():
        for _ in range(50):
            for emoji in anim:
                try:
                    bot.edit_message_text(f"{text} {emoji}", cid, msg.message_id)
                    time.sleep(0.7)
                except: pass
    threading.Thread(target=animate, daemon=True).start()
    return msg

def stop_loading(cid, mid):
    if cid in loading:
        loading.pop(cid)
    try: bot.delete_message(cid, mid)
    except: pass

# ======== ГОЛОВНЕ МЕНЮ ========
def main_menu():
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.row("Профиль")
    k.row("Генератор Медіа", "Морські новини")
    k.row("Створити презентацію", "Відповіді на питання")
    return k

# ======== /start — ТВІЙ ПРОФІЛЬ ========
@bot.message_handler(commands=["start"])
def start(m):
    cid = m.chat.id
    username = m.from_user.username or "Капітан"
    uid = m.from_user.id
    reg_date = "2025-11-09"

    if cid not in user_data:
        user_data[cid] = {
            "reg_date": reg_date,
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
        f"<b>⚓ КАПІТАН @Artem1488962 НА МОСТИКУ!</b>\n\n"
        f"🆔 ID: <code>1474031301</code>\n"
        f"📅 Дата: <b>{reg_date}</b>\n"
        f"🌍 Країна: <b>UA</b>\n\n"
        "🚢 <b>Найпотужніший морський AI-бот</b>\n"
        "• Фото: 2 сек\n"
        "• Відео: 18 сек\n"
        "• Презентації NatGeo\n"
        "• Погода з хвилями\n\n"
        "<i>Слава ЗСУ!</i>",
        reply_markup=main_menu())

# ======== ПРОФІЛЬ ========
@bot.message_handler(func=lambda m: m.text == "Профиль")
def profile(m):
    cid = m.chat.id
    u = user_data[cid]
    text = f"""
<b>⚓ Твій морський профіль</b>
🆔 ID: <code>1474031301</code>
👤 Username: <b>@Artem1488962</b>
📅 Дата: <b>2025-11-09</b>
🌍 Країна: <b>UA</b>

<b>📊 Статистика:</b>
❓ Питань: {len(u['questions'])}
📸 Фото: {len(u['media'])}
🎬 Відео: {len(u['video'])}
🎨 Презентацій: {len(u['pres'])}
🌊 Новин: {len(u['news'])}
🌤 Погоди: {len(u['weather'])}
💬 Відповідей: {len(u['answers'])}
    """.strip()

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("❓ Питання", callback_data="h_q"),
        types.InlineKeyboardButton("📸 Фото", callback_data="h_m"),
        types.InlineKeyboardButton("🎬 Відео", callback_data="h_v"),
        types.InlineKeyboardButton("🎨 Презентації", callback_data="h_p"),
        types.InlineKeyboardButton("🌊 Новини", callback_data="h_n"),
        types.InlineKeyboardButton("💬 Відповіді", callback_data="h_a")
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
    title = {"q":"Питання", "m":"Фото", "v":"Відео", "p":"Презентації", "n":"Новини", "a":"Відповіді"}[t]
    text = f"<b>{title} (останні 10):</b>\n\n"
    for i, x in enumerate(items, 1):
        short = x[:60] + "..." if len(x) > 60 else x
        text += f"{i}. <code>{short}</code>\n"
    bot.send_message(cid, text)

# ======== ГЕНЕРАТОР МЕДІА ========
@bot.message_handler(func=lambda m: m.text == "Генератор Медіа")
def media_menu(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("📸 Фото", "🎬 Відео")
    k.row("⬅️ Назад")
    bot.send_message(m.chat.id, "Що створюємо, капітане?", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["📸 Фото", "🎬 Відео"])
def ask_prompt(m):
    example_ru = "ЗСУ на палубі, захід сонця, фотореалізм" if "Фото" in m.text else "корабель у штормі, 10 сек"
    bot.send_message(m.chat.id,
        f"Опиши {m.text[2:].lower()}:\n\n"
        f"Приклад: <i>«{example_ru}»</i>\n"
        "Можна українською!",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, generate_photo if "Фото" in m.text else generate_video)

def generate_photo(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["media"].append(prompt)
    load = start_loading(cid, "Генерую фото")
    try:
        r = requests.post("https://api.klingai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {KLING_API_KEY}"},
            json={"prompt": prompt, "n": 1, "size": "1024x1024"}
        ).json()
        img_url = r["data"][0]["url"]
        stop_loading(cid, load.message_id)
        bot.send_photo(cid, img_url, caption=f"📸 {prompt}")
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, f"Помилка: {e}\nСпробуй ще раз через 20 сек")

def generate_video(m):
    cid = m.chat.id
    prompt = m.text
    user_data[cid]["video"].append(prompt)
    load = start_loading(cid, "Створюю відео")
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
        bot.send_message(cid, "Відео в обробці, скоро надійде!")
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, f"Помилка: {e}")

# ======== МОРСЬКІ НОВИНИ ========
@bot.message_handler(func=lambda m: m.text == "Морські новини")
def news(m):
    cid = m.chat.id
    load = start_loading(cid, "Шукаю новини")
    model = genai.GenerativeModel("gemini-1.5-pro")
    try:
        resp = model.generate_content("""
        Знайди 3 головні морські новини за останні 24 години.
        Для кожної:
        - Заголовок
        - 2 речення
        - Фото (.jpg/.png)
        - Відео YouTube
        - Джерело (URL)
        Формат: Markdown
        """)
        stop_loading(cid, load.message_id)
        bot.send_message(cid, resp.text, disable_web_page_preview=False)
        user_data[cid]["news"].append(datetime.now().strftime("%H:%M"))
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Новини тимчасово недоступні")

# ======== ПРЕЗЕНТАЦІЇ ========
@bot.message_handler(func=lambda m: m.text == "Створити презентацію")
def create_presentation(m):
    bot.send_message(m.chat.id, "Опиши тему презентації:\nПриклад: «Український флот у Чорному морі»")
    bot.register_next_step_handler(m, generate_presentation)

def generate_presentation(m):
    cid = m.chat.id
    topic = m.text
    user_data[cid]["pres"].append(topic)
    load = start_loading(cid, "Створюю презентацію")
    model = genai.GenerativeModel("gemini-1.5-pro")
    try:
        resp = model.generate_content(f"""
        Створи презентацію: "{topic}"
        5 слайдів:
        - Заголовок
        - 3 пункти
        - Фото (опис)
        - Колір фону (hex)
        Стиль: National Geographic
        """)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"{topic}", ln=1, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", "", 12)
        for line in resp.text.split("\n"):
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
        bot.send_message(cid, "Помилка генерації PDF")

# ======== ВІДПОВІДІ НА ПИТАННЯ ========
@bot.message_handler(func=lambda m: m.text == "Відповіді на питання")
def ask_question(m):
    bot.send_message(m.chat.id, "Задайте питання:\nПриклад: «Яке майбутнє ЗСУ на морі?»")
    bot.register_next_step_handler(m, answer_question)

def answer_question(m):
    cid = m.chat.id
    q = m.text
    user_data[cid]["questions"].append(q)
    user_data[cid]["answers"].append(q)
    load = start_loading(cid, "Шукаю відповідь")
    model = genai.GenerativeModel("gemini-1.5-pro")
    try:
        resp = model.generate_content(f"""
        Відповідай на питання: "{q}"
        - 3 абзаци
        - Фото (опис)
        - Відео YouTube
        - 2 джерела (URL)
        """)
        stop_loading(cid, load.message_id)
        bot.send_message(cid, resp.text, disable_web_page_preview=False)
    except:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "Не вдалося відповісти")

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    bot.send_message(m.chat.id, "Головне меню", reply_markup=main_menu())

# ======== FLASK ========
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    print("Бот запущено! Слава ЗСУ!")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
