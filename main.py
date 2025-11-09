import os
import time
import threading
import base64
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import feedparser
import google.generativeai as genai

# ==========================
# 🔐 Настройки API
# ==========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") or "https://tg-bot-final-1.onrender.com"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# ==========================
# 💡 Модели
# ==========================
MODEL_TEXT = "models/gemini-2.5-pro"
MODEL_IMAGE = "models/imagen-4.0-generate-001"

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)
user_history = {}

# ==========================
# 🔄 Антифриз Render
# ==========================
def keep_alive():
    import requests
    while True:
        try:
            requests.get(WEBHOOK_HOST)
            print("💤 Ping → Render OK")
        except Exception as e:
            print("⚠️ Ping Error:", e)
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

# ==========================
# 📱 Главное меню
# ==========================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль")
    markup.row("🖼️ Генератор Медиа", "⚓ Морские новости")
    markup.row("🎨 Создать презентацию", "❓ Ответы на вопросы")
    return markup

# ==========================
# /start
# ==========================
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_history.setdefault(chat_id, {"questions": [], "media": [], "presentations": [], "news": []})
    bot.send_message(chat_id, f"Привет, {message.from_user.first_name}! 👋\nВыбери опцию:", reply_markup=main_menu())

# ==========================
# 👤 Профиль
# ==========================
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    chat_id = message.chat.id
    hist = user_history.get(chat_id, {})
    text = (
        f"<b>Твой профиль</b>\n"
        f"🆔 ID: <code>{chat_id}</code>\n"
        f"👤 Username: @{message.from_user.username}\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"📊 Вопросов: {len(hist['questions'])}\n"
        f"🖼️ Медиа: {len(hist['media'])}\n"
        f"📘 Презентаций: {len(hist['presentations'])}\n"
        f"⚓ Новостей: {len(hist['news'])}"
    )
    bot.send_message(chat_id, text, reply_markup=main_menu())

# ==========================
# 🖼️ Генератор Медиа
# ==========================
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Фото", "🎬 Видео (в разработке)")
    markup.row("⬅️ Назад в меню")
    bot.send_message(message.chat.id, "Выберите тип медиа:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📸 Фото")
def ask_image_prompt(message):
    msg = bot.send_message(message.chat.id, "✏️ Введите описание (например: «кот в скафандре на Марсе, реалистично»)")
    bot.register_next_step_handler(msg, generate_image)

def generate_image(message):
    chat_id = message.chat.id
    prompt = message.text
    bot.send_message(chat_id, "🔄 Генерирую фото через Imagen 4.0... 🪄")

    try:
        model = genai.GenerativeModel(MODEL_IMAGE)
        result = model.predict({"prompt": prompt})
        if "images" not in result or not result["images"]:
            raise ValueError("Не получено изображение")

        image_base64 = result["images"][0]["image_base64"]
        image_bytes = base64.b64decode(image_base64)
        filename = f"generated_{chat_id}.png"
        with open(filename, "wb") as f:
            f.write(image_bytes)

        bot.send_photo(chat_id, open(filename, "rb"))
        user_history[chat_id]["media"].append(prompt)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при генерации изображения: {e}")

# ==========================
# ⚓ Морские новости
# ==========================
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🌊 Получаю актуальные морские новости...")
    feed = feedparser.parse("https://news.un.org/feed/subscribe/ru/news/topic/sea/feed/rss.xml")
    for e in feed.entries[:3]:
        bot.send_message(chat_id, f"<b>{e.title}</b>\n{e.link}")
    user_history[chat_id]["news"].append(datetime.now())

# ==========================
# 🎨 Презентации
# ==========================
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🎨 Создаю журнальную презентацию через Gemini 2.5 Pro...")

    try:
        model = genai.GenerativeModel(MODEL_TEXT)
        prompt = "Создай презентацию в журнальном стиле о технологиях будущего, с 5 короткими разделами."
        result = model.generate_content(prompt)
        text = result.text or "Ошибка генерации текста."

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.multi_cell(0, 10, "📰 Презентация Gemini 2.5 Pro\n\n" + text)
        filename = f"presentation_{chat_id}.pdf"
        pdf.output(filename)
        bot.send_document(chat_id, open(filename, "rb"))
        user_history[chat_id]["presentations"].append(filename)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка при создании презентации: {e}")

# ==========================
# ❓ Ответы на вопросы
# ==========================
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def ask_question(message):
    msg = bot.send_message(message.chat.id, "💬 Задай вопрос — я отвечу через Gemini 2.5 Pro:")
    bot.register_next_step_handler(msg, answer_question)

def answer_question(message):
    chat_id = message.chat.id
    question = message.text
    bot.send_message(chat_id, "🤔 Думаю над ответом через Gemini 2.5 Pro...")

    try:
        model = genai.GenerativeModel(MODEL_TEXT)
        response = model.generate_content(question)
        bot.send_message(chat_id, response.text or "❌ Не удалось получить ответ.")
        user_history[chat_id]["questions"].append(question)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка при ответе: {e}")

# ==========================
# 🌍 Flask сервер
# ==========================
@app.route("/", methods=["GET"])
def index():
    return "🤖 Бот работает на Render!", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

# ==========================
# 🚀 Запуск
# ==========================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
