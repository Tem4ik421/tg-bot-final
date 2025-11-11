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
    example = "Кіт на даху, захід сонця, фотореализм" if "Фото" in m.text else "Кіт танцює, 10 сек, анімація"
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
    start_progress(cid, "ГЕНЕРУЮ ФОТО")

    if not REPLICATE_API_TOKEN:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Replicate API не налаштований.", reply_markup=main_menu())
        return

    try:
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt + ", photorealistic, 8K, ultra detailed, cinematic lighting, high quality, masterpiece",
                "num_outputs": 1,
                "width": 1024,
                "height": 1024,
                "num_inference_steps": 4
            }
        )
        img_url = output[0]
        stop_progress(cid)
        bot.send_photo(cid, img_url, caption=f"<b>ФОТО:</b> {prompt}", reply_markup=main_menu())
    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, f"[Error] Помилка: {str(e)[:100]}", reply_markup=main_menu())

# === ВІДЕО ===
def generate_video(m):
    cid = m.chat.id
    prompt = m.text.strip().strip('«»"')
    user_data.setdefault(cid, {})["video"].append(prompt)
    start_progress(cid, "СТВОРЮЮ ВІДЕО")

    if not REPLICATE_API_TOKEN:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Replicate API не налаштований.", reply_markup=main_menu())
        return

    try:
        image_output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt + ", cinematic keyframe, 4K, ultra realistic, sharp, masterpiece",
                "num_outputs": 1,
                "width": 1024,
                "height": 576,
                "num_inference_steps": 4
            }
        )
        image_url = image_output
