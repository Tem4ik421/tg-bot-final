import os
import threading
import time
import base64
import requests
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import feedparser
import google.generativeai as genai

# === Ключи ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например: https://tg-bot-final-1.onrender.com
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

genai.configure(api_key=GEMINI_API_KEY)
MODEL_TEXT = "gemini-2.0-pro"
MODEL_IMAGE = "imagen-3.0"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)
user_history = {}

# === Главное меню ===
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль")
    markup.row("🖼️ Генератор Медиа", "⚓ Морские новости")
    markup.row("🎨 Создать презентацию", "❓ Ответы на вопросы")
    return markup

# === /start ===
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_history.setdefault(chat_id, {"questions": [], "media": [], "presentations": [], "news": []})
    bot.send_message(chat_id, f"Привет, {message.from_user.first_name}! 👋\nВыбери опцию из меню:", reply_markup=main_menu())

# === Анимация загрузки ===
def loading_animation(chat_id, text, seconds=5):
    for i in range(seconds):
        dots = "." * ((i % 3) + 1)
        try:
            bot.edit_message_text(f"{text}{dots}", chat_id, bot.send_message(chat_id, text).message_id)
        except:
            pass
        time.sleep(0.7)

# === Профиль ===
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    chat_id = message.chat.id
    hist = user_history.get(chat_id, {})
    text = (
        f"<b>Твой профиль</b>\n"
        f"ID: <code>{chat_id}</code>\n"
        f"Username: @{message.from_user.username}\n"
        f"Дата: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"📊 Вопросов: {len(hist['questions'])}\n"
        f"🖼️ Медиа: {len(hist['media'])}\n"
        f"📘 Презентаций: {len(hist['presentations'])}\n"
        f"⚓ Новостей: {len(hist['news'])}"
    )
    bot.send_message(chat_id, text, reply_markup=main_menu())

# === Генератор медиа ===
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Фото", "🎬 Видео")
    markup.row("⬅️ Назад в меню")
    bot.send_message(message.chat.id, "Выберите тип медиа:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📸 Фото")
def ask_photo_prompt(message):
    bot.send_message(message.chat.id, "✏️ Введите описание (например: «кот в скафандре на Марсе, реалистично»)")
    bot.register_next_step_handler(message, generate_photo)

def generate_photo(message):
    chat_id = message.chat.id
    prompt = message.text
    bot.send_message(chat_id, "🔄 Генерирую фото через Imagen 3.0... 🪄")
    try:
        model = genai.GenerativeModel(MODEL_IMAGE)
        result = model.generate_content(prompt)
        image_base64 = result.candidates[0].content.parts[0].inline_data.data
        file_path = f"photo_{chat_id}.png"
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(image_base64))
        bot.send_photo(chat_id, open(file_path, "rb"), caption=f"🖼️ {prompt}")
        user_history[chat_id]["media"].append(prompt)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при генерации: {e}", reply_markup=main_menu())

# === Презентации ===
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "🎨 Создаю журнальную презентацию... ⏳")
    threading.Thread(target=loading_animation, args=(chat_id, "🖋️ Оформляю страницы", 6), daemon=True).start()
    try:
        model = genai.GenerativeModel(MODEL_TEXT)
        result = model.generate_content("Создай красивую презентацию о будущем морских технологий в журнальном стиле.")
        text = result.text
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.multi_cell(0, 10, text)
        file_name = f"presentation_{chat_id}.pdf"
        pdf.output(file_name)
        user_history[chat_id]["presentations"].append(file_name)
        bot.send_document(chat_id, open(file_name, "rb"), caption="📘 Готово!")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка при создании: {e}")

# === Морские новости ===
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🌊 Получаю актуальные морские новости...")
    try:
        feed = feedparser.parse("https://news.un.org/feed/subscribe/ru/news/topic/sea/feed/rss.xml")
        for e in feed.entries[:3]:
            bot.send_message(chat_id, f"<b>{e.title}</b>\n{e.link}")
        user_history[chat_id]["news"].append(datetime.now())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при получении новостей: {e}")

# === Ответы на вопросы ===
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def ask_question(message):
    bot.send_message(message.chat.id, "💬 Задай вопрос — я отвечу через Gemini 2.0 Pro.")
    bot.register_next_step_handler(message, answer_question)

def answer_question(message):
    chat_id = message.chat.id
    question = message.text
    bot.send_message(chat_id, "🤔 Думаю над ответом...")
    try:
        model = genai.GenerativeModel(MODEL_TEXT)
        result = model.generate_content(question)
        bot.send_message(chat_id, f"💡 Ответ:\n{result.text}", reply_markup=main_menu())
        user_history[chat_id]["questions"].append(question)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при генерации: {e}", reply_markup=main_menu())

# === Flask сервер ===
@app.route("/", methods=["GET"])
def index():
    return "🤖 Telegram бот активен на Render!", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

# === Keep-Alive (анти-сон Render) ===
def keep_alive():
    while True:
        try:
            requests.get(WEBHOOK_HOST)
            print(f"💓 Ping {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"⚠️ Ошибка пинга: {e}")
        time.sleep(300)

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
