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
import replicate

# ======== КОНФІГ ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Ініціалізація
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if REPLICATE_API_TOKEN:
    replicate.Client(api_token=REPLICATE_API_TOKEN)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)
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

# ======== ГРАДІЄНТНА ПРОГРЕС-ПОЛОСКА ========
def gradient_bar(percent, width=20):
    colors = ["Red", "Orange", "Yellow", "Green", "Blue", "Purple"]
    idx = min(int(percent / 100 * len(colors)), len(colors)-1)
    filled = int(width * percent // 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"<code>{bar}</code> <b>{percent}% {colors[idx]}</b>"

def start_gradient(cid, text="Генерую"):
    msg = bot.send_message(cid, f"<b>{text}</b>\n{gradient_bar(0)}")
    loading[cid] = {"msg_id": msg.message_id, "type": "gradient"}
    
    def update():
        for p in range(0, 101, 5):
            if cid not in loading or loading[cid].get("stop"):
                break
            try:
                bot.edit_message_text(
                    f"<b>{text}</b>\n{gradient_bar(p)}",
                    cid, loading[cid]["msg_id"]
                )
            except:
                pass
            time.sleep(0.25)
    threading.Thread(target=update, daemon=True).start()
    return msg

def stop_gradient(cid):
    if cid in loading and loading[cid].get("type") == "gradient":
        loading[cid]["stop"] = True
        time.sleep(0.5)
        try:
            bot.delete_message(cid, loading[cid]["msg_id"])
        except:
            pass
        loading.pop(cid, None)

# ======== ГОЛОВНЕ МЕНЮ ========
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
        "<b>КАПІТАН @Tem4ik4751 НА МОСТИКУ!</b>\n"
        "ID: <code>1474031301</code>\n"
        "Бот працює 24/7 — <b>СЛАВА ЗСУ!</b>\n\n"
        "<b>Обери функцію</b>",
        reply_markup=main_menu())

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
<b>МОРСЬКИЙ ПРОФІЛЬ</b>
ID: <code>1474031301</code>
<b>Статистика:</b>
Питань: {len(u.get('questions', []))}
Фото: {len(u.get('media', []))}
Відео: {len(u.get('video', []))}
Презентацій: {len(u.get('pres', []))}
Новин: {len(u.get('news', []))}
Відповідей: {len(u.get('answers', []))}
    """.strip(), reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("h_"))
def history(c):
    cid = c.message.chat.id
    t = c.data[2:]
    maps = {"q":"questions", "m":"media", "v":"video", "p":"pres", "n":"news", "a":"answers"}
    items = user_data.get(cid, {}).get(maps.get(t, ""), [])[-10:]
    if not items:
        bot.answer_callback_query(c.id, "Пусто!", show_alert=True)
        return
    title = {"q":"Питання", "m":"Фото", "v":"Відео", "p":"Презентації", "n":"Новини", "a":"Відповіді"}[t]
    text = f"<b>{title} (останні 10):</b>\n\n"
    for i, x in enumerate(items, 1):
        text += f"{i}. <code>{x[:50]}{'...' if len(x)>50 else ''}</code>\n"
    bot.send_message(cid, text, reply_markup=main_menu())

# ======== ГЕНЕРАТОР МЕДІА ========
@bot.message_handler(func=lambda m: m.text == "Генератор Медіа")
def media_menu(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("Фото", "Відео")
    k.row("Назад")
    bot.send_message(m.chat.id, "<b>ОБЕРИ ЗБРОЮ, КАПІТАНЕ!</b>", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Відео"])
def ask_prompt(m):
    media_type = "фото" if "Фото" in m.text else "відео"
    example = "ЗСУ на палубе, закат, фотореализм" if "Фото" in m.text else "ЗСУ на палубе, закат, 10 сек"
    bot.send_message(m.chat.id,
        f"<b>ОПИШИ {media_type.upper()}:</b>\n"
        f"Приклад: <code>{example}</code>",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, generate_photo if "Фото" in m.text else generate_video)

# === ФОТО: ПРАЦЮЄ 100% ===
def generate_photo(m):
    cid = m.chat.id
    prompt = m.text.strip().strip('«»"')
    user_data.setdefault(cid, {})["media"].append(prompt)
    load = start_gradient(cid, "ГЕНЕРУЮ ФОТО")

    if not REPLICATE_API_TOKEN:
        stop_gradient(cid)
        bot.send_message(cid, "[Warning] Replicate API не налаштований.", reply_markup=main_menu())
        return

    try:
        output = replicate.run(
            "black-forest-labs/flux-schnell:latest",  # ФІКС: додано :latest
            input={
                "prompt": prompt + ", photorealistic, 8K, ultra detailed, cinematic lighting, high quality",
                "num_outputs": 1,
                "width": 1024,
                "height": 1024,
                "num_inference_steps": 4
            }
        )
        img_url = output[0]
        stop_gradient(cid)
        bot.send_photo(cid, img_url, caption=f"<b>ФОТО:</b> {prompt}", reply_markup=main_menu())
    except Exception as e:
        stop_gradient(cid)
        bot.send_message(cid, f"[Error] Помилка фото: {str(e)[:100]}", reply_markup=main_menu())

# === ВІДЕО ===
def generate_video(m):
    cid = m.chat.id
    prompt = m.text.strip().strip('«»"')
    user_data.setdefault(cid, {})["video"].append(prompt)
    load = start_gradient(cid, "СТВОРЮЮ ВІДЕО")

    if not REPLICATE_API_TOKEN:
        stop_gradient(cid)
        bot.send_message(cid, "[Warning] Replicate API не налаштований.", reply_markup=main_menu())
        return

    try:
        image_output = replicate.run(
            "black-forest-labs/flux-schnell:latest",
            input={
                "prompt": prompt + ", cinematic keyframe, 4K, ultra realistic, sharp",
                "num_outputs": 1,
                "width": 1024,
                "height": 576,
                "num_inference_steps": 4
            }
        )
        image_url = image_output[0]

        video_output = replicate.run(
            "stability-ai/stable-video-diffusion-img2vid-xt",
            input={
                "image": image_url,
                "motion_bucket_id": 127,
                "fps": 7,
                "noise_aug_strength": 0.02
            }
        )
        video_url = video_output[0]
        stop_gradient(cid)
        bot.send_video(cid, video_url, caption=f"<b>ВІДЕО:</b> {prompt}", reply_markup=main_menu())
    except Exception as e:
        stop_gradient(cid)
        bot.send_message(cid, f"[Error] Помилка відео: {str(e)[:100]}", reply_markup=main_menu())

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    bot.send_message(m.chat.id, "<b>ГОЛОВНЕ МЕНЮ</b>", reply_markup=main_menu())

# ======== МОРСЬКІ НОВИНИ ========
@bot.message_handler(func=lambda m: m.text == "Морські новини")
def news(m):
    cid = m.chat.id
    load = start_gradient(cid, "ШУКАЮ НОВИНИ")
    if not groq_client:
        stop_gradient(cid)
        bot.send_message(cid, "[Warning] GROQ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": "3 головні морські новини за 24 год: заголовок, 2 речення, фото, відео YouTube, джерело. Markdown."}],
            max_tokens=1000
        )
        stop_gradient(cid)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
        user_data.setdefault(cid, {})["news"].append(time.strftime("%H:%M"))
    except Exception as e:
        stop_gradient(cid)
        bot.send_message(cid, "[Error] GROQ тимчасово недоступний.", reply_markup=main_menu())

# ======== ПРЕЗЕНТАЦІЯ ========
@bot.message_handler(func=lambda m: m.text == "Створити презентацію")
def create_pres(m):
    bot.send_message(m.chat.id, "<b>ТЕМА ПРЕЗЕНТАЦІЇ?</b>\nПриклад: <code>Перемога ЗСУ на морі</code>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, gen_pres)

def gen_pres(m):
    cid = m.chat.id
    topic = m.text.strip()
    user_data.setdefault(cid, {})["pres"].append(topic)
    load = start_gradient(cid, "СТВОРЮЮ PDF")
    if not groq_client:
        stop_gradient(cid)
        bot.send_message(cid, "[Warning] GROQ не налаштований.", reply_markup=main_menu())
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
        stop_gradient(cid)
        bot.send_document(cid, buffer, caption=f"<b>{topic}</b>", filename=f"{topic[:50]}.pdf", reply_markup=main_menu())
    except Exception as e:
        stop_gradient(cid)
        bot.send_message(cid, "[Error] Помилка створення PDF.", reply_markup=main_menu())

# ======== ПИТАННЯ ========
@bot.message_handler(func=lambda m: m.text == "Відповіді на питання")
def ask_q(m):
    bot.send_message(m.chat.id, "<b>ЗАДАЙ ПИТАННЯ:</b>\nПриклад: <code>Коли ЗСУ звільнять Крим?</code>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, answer_q)

def answer_q(m):
    cid = m.chat.id
    q = m.text.strip()
    user_data.setdefault(cid, {})["questions"].append(q)
    load = start_gradient(cid, "ДУМАЮ...")
    if not groq_client:
        stop_gradient(cid)
        bot.send_message(cid, "[Warning] GROQ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": f"Відповідь: {q}. 3 абзаци, фото, відео YouTube, 2 джерела."}],
            max_tokens=1200
        )
        stop_gradient(cid)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
    except Exception as e:
        stop_gradient(cid)
        bot.send_message(cid, "[Error] GROQ перевантажено.", reply_markup=main_menu())

# ======== FLASK WEBHOOK ========
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return '', 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        print(f"ОТРИМАНО UPDATE: {json_string[:200]}")
        update = telebot.types.Update.de_json(json_string)
        if update:
            bot.process_new_updates([update])
        return "OK", 200
    return "", 400

# ======== АВТО-WEBHOOK ========
try:
    info = bot.get_webhook_info()
    if info.url != WEBHOOK_URL:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        print(f"Webhook встановлено: {WEBHOOK_URL}")
    else:
        print(f"Webhook активний: {info.url}")
except Exception as e:
    print(f"Помилка webhook: {e}")

print("Бот запущено! Слава ЗСУ!")
