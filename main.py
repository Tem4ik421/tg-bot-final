import os
import base64
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import feedparser
import google.generativeai as genai

# ======== Настройки окружения ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например https://tg-bot-final.onrender.com
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# ======== Инициализация ========
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ======== Настройка Gemini ========
genai.configure(api_key=GEMINI_API_KEY)

# используем новую модель Gemini 2.5 Pro
MODEL_TEXT = "gemini-2.5-pro-latest"
MODEL_IMAGE = "gemini-2.5-pro-latest"

model_text = genai.GenerativeModel(MODEL_TEXT)
model_image = genai.GenerativeModel(MODEL_IMAGE)

# ======== Хранилище ========
user_history = {}

# ======== Главное меню ========
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль")
    markup.row("🖼️ Генератор Медиа", "⚓ Морские новости")
    markup.row("🎨 Создать презентацию", "❓ Ответы на вопросы")
    return markup

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_history.setdefault(chat_id, {"questions": [], "media": [], "presentations": [], "news": []})
    bot.send_message(chat_id, f"Привет, {message.from_user.first_name}! 👋\nВыбери опцию из меню:", reply_markup=main_menu())

# ======== Профиль ========
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

# ======== Генератор медиа ========
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Фото", "🎬 Видео")
    markup.row("⬅️ Назад в меню")
    bot.send_message(message.chat.id, "Выберите тип медиа:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["📸 Фото", "🎬 Видео"])
def generate_media(message):
    chat_id = message.chat.id
    kind = "фото" if "Фото" in message.text else "видео"
    bot.send_message(chat_id, f"🔄 Генерирую {kind} через Gemini 2.5 Pro... 🪄")
    try:
        prompt = f"Generate a realistic {kind} about the sea, ships, and marine technology, cinematic style."
        response = model_image.generate_content(prompt)
        image_data = base64.b64decode(response.candidates[0].content.parts[0].inline_data.data)
        filename = f"media_{chat_id}.jpg"
        with open(filename, "wb") as f:
            f.write(image_data)
        bot.send_photo(chat_id, open(filename, "rb"), caption=f"✅ {kind.capitalize()} готово!")
        user_history[chat_id]["media"].append(filename)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при генерации: {e}", reply_markup=main_menu())

# ======== Презентация ========
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🎨 Создаю журнальную презентацию через Gemini 2.5 Pro...")
    try:
        response = model_text.generate_content("Создай короткую журнальную статью о технологиях моря и навигации.")
        text = response.text.strip()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 18)
        pdf.multi_cell(0, 10, "📰 Журнальная презентация\n\n", align="C")
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, text)
        filename = f"presentation_{chat_id}.pdf"
        pdf.output(filename)
        bot.send_document(chat_id, open(filename, "rb"), caption="📘 Готово!", reply_markup=main_menu())
        user_history[chat_id]["presentations"].append(filename)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при создании презентации: {e}")

# ======== Морские новости ========
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🌊 Получаю актуальные морские новости...")
    feed = feedparser.parse("https://news.un.org/feed/subscribe/ru/news/topic/sea/feed/rss.xml")
    for e in feed.entries[:3]:
        bot.send_message(chat_id, f"<b>{e.title}</b>\n{e.link}")
    user_history[chat_id]["news"].append(datetime.now())

# ======== Ответы на вопросы ========
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def question_start(message):
    bot.send_message(message.chat.id, "💬 Задай вопрос, и я отвечу через Gemini 2.5 Pro!")

@bot.message_handler(func=lambda m: m.text not in ["⬅️ Назад в меню"])
def answer_question(message):
    chat_id = message.chat.id
    user_history[chat_id]["questions"].append(message.text)
    try:
        response = model_text.generate_content(message.text)
        bot.send_message(chat_id, f"🤖 {response.text}", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обращении к Gemini: {e}")

# ======== Flask ========
@app.route("/", methods=["GET"])
def index():
    return "🤖 Бот работает на Render (Gemini 2.5 Pro)", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
