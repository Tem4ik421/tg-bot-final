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

# ======== АНІМАЦІЯ ========
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
        "<b>Капитан @Tem4ik4751 на мостике!</b>\n"
        "ID: <code>1474031301</code>\n"
        "Бот працює 24/7 — <b>Слава ЗСУ!</b>\n\n"
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
<b>Морський профіль</b>
ID: <code>1474031301</code>
<b>Статистика:</b>
[Question] Питань: {len(u.get('questions', []))}
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
    bot.send_message(m.chat.id, "Обери зброю, капітане!", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Відео"])
def ask_prompt(m):
    media_type = "фото" if "Фото" in m.text else "відео"
    example = "ЗСУ на палубе, закат, фотореализм" if "Фото" in m.text else "ЗСУ на палубе, закат, 10 сек"
    bot.send_message(m.chat.id,
        f"Опиши {media_type}:\n"
        f"Приклад: «{example}»",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, generate_photo if "Фото" in m.text else generate_video)

# === ФОТО: FLUX.SCHNELL (ФІКС: :latest) ===
def generate_photo(m):
    cid = m.chat.id
    prompt = m.text
    user_data.setdefault(cid, {})["media"].append(prompt)
    load = start_loading(cid, "Генерую фото")

    if not REPLICATE_API_TOKEN:
        stop_loading(cid, load.message_id)
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
        stop_loading(cid, load.message_id)
        bot.send_photo(cid, img_url, caption=f"[Camera] {prompt}", reply_markup=main_menu())
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, f"[Error] Помилка фото: {str(e)[:100]}", reply_markup=main_menu())

# === ВІДЕО: FLUX + STABLE VIDEO (ФІКС: :latest) ===
def generate_video(m):
    cid = m.chat.id
    prompt = m.text
    user_data.setdefault(cid, {})["video"].append(prompt)
    load = start_loading(cid, "Створюю відео")

    if not REPLICATE_API_TOKEN:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "[Warning] Replicate API не налаштований.", reply_markup=main_menu())
        return

    try:
        # Ключова рамка
        image_output = replicate.run(
            "black-forest-labs/flux-schnell:latest",  # ФІКС: додано :latest
            input={
                "prompt": prompt + ", cinematic keyframe, 4K, ultra realistic, sharp",
                "num_outputs": 1,
                "width": 1024,
                "height": 576,
                "num_inference_steps": 4
            }
        )
        image_url = image_output[0]

        # Відео
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
        stop_loading(cid, load.message_id)
        bot.send_video(cid, video_url, caption=f"[Film] {prompt}", reply_markup=main_menu())
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, f"[Error] Помилка відео: {str(e)[:100]}", reply_markup=main_menu())

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    bot.send_message(m.chat.id, "Головне меню", reply_markup=main_menu())

# ======== МОРСЬКІ НОВИНИ ========
@bot.message_handler(func=lambda m: m.text == "Морські новини")
def news(m):
    cid = m.chat.id
    load = start_loading(cid, "Шукаю новини")
    if not groq_client:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "[Warning] GROQ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": "3 головні морські новини за 24 год: заголовок, 2 речення, фото, відео YouTube, джерело. Markdown."}],
            max_tokens=1000
        )
        stop_loading(cid, load.message_id)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
        user_data.setdefault(cid, {})["news"].append(time.strftime("%H:%M"))
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "[Error] GROQ тимчасово недоступний.", reply_markup=main_menu())

# ======== ПРЕЗЕНТАЦІЯ ========
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
        stop_loading(cid, load.message_id)
        bot.send_document(cid, buffer, caption=topic, filename=f"{topic[:50]}.pdf", reply_markup=main_menu())
    except Exception as e:
        stop_loading(cid, load.message_id)
        bot.send_message(cid, "[Error] Помилка створення PDF.", reply_markup=main_menu())

# ======== ПИТАННЯ ========
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
        bot.send_message(cid, "[Warning] GROQ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": f"Відповідь: {q}. 3 абзаци, фото, відео YouTube, 2 джерела."}],
            max_tokens=1200
        )
        stop_loading(cid, load.message_id)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
    except Exception as e:
        stop_loading(cid, load.message_id)
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
    print("Bad content-type!")
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
