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
from gradio_client import Client # Переконайся, що 'gradio_client' є у requirements.txt

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

# ======== БІЛА ПРОГРЕС-ПОЛОСКА (1% КРОК) ========
def progress_bar(percent, width=20):
    filled = int(width * percent // 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"<code>{bar}</code> <b>{percent}%</b>"

def start_progress(cid, text="Генерую"):
    msg = bot.send_message(cid, f"<b>{text}</b>\n{progress_bar(0)}")
    loading[cid] = {"msg_id": msg.message_id, "type": "progress"}
    
    def update():
        for p in range(1, 101):
            if cid not in loading or loading[cid].get("stop"):
                break
            try:
                bot.edit_message_text(
                    f"<b>{text}</b>\n{progress_bar(p)}",
                    cid, loading[cid]["msg_id"]
                )
            except:
                pass
            time.sleep(0.05)
    threading.Thread(target=update, daemon=True).start()

def stop_progress(cid):
    if cid in loading and loading[cid].get("type") == "progress":
        loading[cid]["stop"] = True
        time.sleep(0.1)
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

# -------------------------------------------------------------------
# ✅ ФУНКЦІЯ АВТО-ПЕРЕКЛАДУ
# -------------------------------------------------------------------
def translate_to_english(text_to_translate):
    """Перекладає текст на англійську, використовуючи Groq (Llama 3.1 8B)."""
    if not groq_client:
        print("Попередження: Groq API не налаштований, переклад неможливий.")
        return text_to_translate 

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a translation assistant. Translate the user's text to English. Return ONLY the translated text, nothing else. Do not add quotation marks."
                },
                {
                    "role": "user",
                    "content": text_to_translate
                }
            ],
            max_tokens=300,
            temperature=0.0
        )
        translated_text = completion.choices[0].message.content.strip().strip('"')
        
        if translated_text:
            print(f"Переклад: '{text_to_translate}' -> '{translated_text}'")
            return translated_text
        else:
            return text_to_translate
    except Exception as e:
        print(f"Помилка перекладу: {e}")
        return text_to_translate

# -------------------------------------------------------------------
# ✅ ЗАХИСНА ФУНКЦІЯ
# -------------------------------------------------------------------
def ensure_user_data(cid):
    """Гарантує, що повна структура даних існує для користувача."""
    user_data.setdefault(cid, {})
    keys_to_init = ["questions", "media", "video", "pres", "news", "answers"]
    for key in keys_to_init:
        user_data[cid].setdefault(key, [])

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(m):
    cid = m.chat.id
    ensure_user_data(cid) 
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
    ensure_user_data(cid) 
    u = user_data.get(cid)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Питання", callback_data="h_q"),
        types.InlineKeyboardButton("Фото", callback_data="h_m"),
        types.InlineKeyboardButton("Відео", callback_data="h_v"),
        types.InlineKeyboardButton("Презентації", callback_data="h_p"),
        types.InlineKeyboardButton("Новини", callback_data="h_n"),
        types.InlineKeyboardButton("Відповіді", callback_data="h_a")
    )
    # -------------------------------------------------------------------
    # ✅ ВИПРАВЛЕНО SYNTAXERROR: прибрано "... (опущены...)"
    # -------------------------------------------------------------------
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
    ensure_user_data(cid)
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
    example = "Кіт на даху, захід сонця, фотореализм" if "Фото" in m.text else "Кіт танцює, 10 сек, анімація"
    bot.send_message(m.chat.id,
        f"<b>ОПИШИ {media_type.upper()}:</b>\n"
        f"Приклад: <code>{example}</code>",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, generate_photo if "Фото" in m.text else generate_video)

# === ФОТО ===
def generate_photo(m):
    cid = m.chat.id
    prompt = m.text.strip().strip('«»"')
    
    ensure_user_data(cid) 
    user_data[cid]["media"].append(prompt) 
    
    start_progress(cid, "ПЕРЕКЛАДАЮ ТА ГЕНЕРУЮ ФОТО (FLUX)") 

    try:
        translated_prompt = translate_to_english(prompt)
        
        client = Client("NihalGazi/FLUX-Unlimited")
        full_prompt = translated_prompt + ", photorealistic, 8K, ultra detailed, cinematic lighting, high quality, masterpiece"
        
        result = client.predict(
            prompt=full_prompt,
            width=1024,
            height=1024,
            seed=0,
            randomize=True,
            server_choice="Google US Server",
            api_name="/generate_image"
        )
        
        img_filepath = result[0]
        stop_progress(cid)
        
        with open(img_filepath, "rb") as photo:
            bot.send_photo(cid, photo, caption=f"<b>ФОТО:</b> {prompt}", reply_markup=main_menu())
        
        if os.path.exists(img_filepath):
            os.remove(img_filepath)

    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, f"[Error] Помилка Gradio: {str(e)[:100]}", reply_markup=main_menu())


# === ВІДЕО ===
def generate_video(m):
    cid = m.chat.id
    prompt = m.text.strip().strip('«»"')

    ensure_user_data(cid) 
    user_data[cid]["video"].append(prompt) 
    
    start_progress(cid, "ПЕРЕКЛАДАЮ ТА СТВОРЮЮ ВІДЕО")

    if not REPLICATE_API_TOKEN:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Replicate API не налаштований.", reply_markup=main_menu())
        return

    try:
        translated_prompt = translate_to_english(prompt)

        image_output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": translated_prompt + ", cinematic keyframe, 4K, ultra realistic, sharp, masterpiece",
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

        stop_progress(cid)
        bot.send_video(cid, video_url, caption=f"<b>ВІДЕО:</b> {prompt}", reply_markup=main_menu())
    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, f"[Error] Помилка відео: {str(e)[:100]}", reply_markup=main_menu())

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    bot.send_message(m.chat.id, "<b>ГОЛОВНЕ МЕНЮ</b>", reply_markup=main_menu())

# ======== МОРСЬКІ НОВИНИ ========
@bot.message_handler(func=lambda m: m.text == "Морські новини")
def news(m):
    cid = m.chat.id
    ensure_user_data(cid) 
    start_progress(cid, "ШУКАЮ НОВИНИ")
    if not groq_client:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] GROQ API ключ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": "3 найцікавіші новини про океан за 24 год: заголовок, 2 речення, фото, відео YouTube, джерело. Markdown."}],
            max_tokens=1000
        )
        stop_progress(cid)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
        user_data[cid]["news"].append(time.strftime("%H:%M"))

    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, "[Error] GROQ тимчасово недоступний.", reply_markup=main_menu())

# ======== ПРЕЗЕНТАЦІЯ ========
@bot.message_handler(func=lambda m: m.text == "Створити презентацію")
def create_pres(m):
    bot.send_message(m.chat.id, "<b>ТЕМА ПРЕЗЕНТАЦІЇ?</b>\nПриклад: <code>Майбутнє штучного інтелекту</code>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, gen_pres)

def gen_pres(m):
    cid = m.chat.id
    topic = m.text.strip()
    ensure_user_data(cid)
    user_data[cid]["pres"].append(topic) 
    
    start_progress(cid, "СТВОРЮЮ PDF")
    if not groq_client:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] GROQ API ключ не налаштований.", reply_markup=main_menu())
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
        stop_progress(cid)
        bot.send_document(cid, buffer, caption=f"<b>{topic}</b>", filename=f"{topic[:50]}.pdf", reply_markup=main_menu())
    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, "[Error] Помилка створення PDF.", reply_markup=main_menu())

# ======== ПИТАННЯ ========
@bot.message_handler(func=lambda m: m.text == "Відповіді на питання")
def ask_q(m):
    bot.send_message(m.chat.id, "<b>ЗАДАЙ ПИТАННЯ:</b>\nПриклад: <code>Коли я стану мільйонером?</code>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, answer_q)

def answer_q(m):
    cid = m.chat.id
    q = m.text.strip()
    ensure_user_data(cid)
    user_data[cid]["questions"].append(q)
    
    start_progress(cid, "ДУМАЮ...")
    if not groq_client:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] GROQ API ключ не налаштований.", reply_markup=main_menu())
        return
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": f"Відповідь: {q}. 3 абзаци, фото, відео YouTube, 2 джерела."}],
            max_tokens=1200
        )
        stop_progress(cid)
        bot.send_message(cid, completion.choices[0].message.content, disable_web_page_preview=False, reply_markup=main_menu())
    except Exception as e:
        stop_progress(cid)
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
