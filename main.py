import os
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import feedparser
import google.generativeai as genai

# ======== Настройки ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например https://tg-bot-final-1.onrender.com
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# ======== Настройка Gemini ========
genai.configure(api_key=GEMINI_API_KEY)
MODEL_TEXT = "gemini-2.5-pro"
MODEL_IMAGE = "gemini-2.5-pro"

# ======== Flask и бот ========
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

user_history = {}
user_state = {}  # для отслеживания состояния (например, ожидаем описание для фото)

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
        f"🆔 ID: <code>{chat_id}</code>\n"
        f"👤 Username: @{message.from_user.username}\n"
        f"📅 Дата: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"📊 Статистика:\n"
        f"📝 Вопросов: {len(hist['questions'])}\n"
        f"🖼️ Медиа: {len(hist['media'])}\n"
        f"📘 Презентаций: {len(hist['presentations'])}\n"
        f"⚓ Новостей: {len(hist['news'])}"
    )
    bot.send_message(chat_id, text, reply_markup=main_menu())


# ======== Генератор Медиа ========
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Фото", "🎬 Видео")
    markup.row("⬅️ Назад в меню")
    bot.send_message(message.chat.id, "Выберите тип медиа:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text in ["📸 Фото", "🎬 Видео"])
def ask_media_description(message):
    chat_id = message.chat.id
    user_state[chat_id] = message.text
    bot.send_message(chat_id, "✏️ Введите описание (например: «кот в скафандре на Марсе, реалистично»)")


@bot.message_handler(func=lambda m: m.chat.id in user_state)
def generate_media(message):
    chat_id = message.chat.id
    kind = "фото" if "Фото" in user_state[chat_id] else "видео"
    prompt = message.text.strip()

    bot.send_message(chat_id, f"🔄 Генерирую {kind} через Gemini 2.5 Pro... 🪄")

    try:
        model = genai.GenerativeModel(MODEL_IMAGE)
        result = model.generate_content(prompt)
        user_history[chat_id]["media"].append(prompt)
        bot.send_message(chat_id, f"✅ {kind.capitalize()} создано!\nОписание: {prompt}", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при генерации: {e}", reply_markup=main_menu())
    finally:
        del user_state[chat_id]


# ======== Создание презентации ========
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🎨 Создаю журнальную презентацию через Gemini 2.5 Pro...")

    try:
        model = genai.GenerativeModel(MODEL_TEXT)
        content = model.generate_content("Создай стильный журнальный текст о будущем морских технологий.")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 18)
        pdf.cell(0, 10, "🌊 Журнальная презентация", ln=True, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, content.text)
        filename = f"presentation_{chat_id}.pdf"
        pdf.output(filename)
        user_history[chat_id]["presentations"].append(filename)
        bot.send_document(chat_id, open(filename, "rb"), reply_markup=main_menu())
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при создании презентации: {e}", reply_markup=main_menu())


# ======== Морские новости ========
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🌊 Получаю актуальные морские новости...")

    try:
        feed = feedparser.parse("https://www.maritime-executive.com/rss/main.xml")
        for e in feed.entries[:3]:
            news_text = f"<b>{e.title}</b>\n{e.link}"
            bot.send_message(chat_id, news_text)
        user_history[chat_id]["news"].append(datetime.now())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка загрузки новостей: {e}")


# ======== Ответы на вопросы ========
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def question_start(message):
    bot.send_message(message.chat.id, "💬 Задай любой вопрос, и я постараюсь ответить! 🌟")


@bot.message_handler(func=lambda m: m.text not in ["⬅️ Назад в меню"])
def answer_question(message):
    chat_id = message.chat.id
    question = message.text
    bot.send_message(chat_id, "🤔 Думаю над ответом через Gemini 2.5 Pro...")

    try:
        model = genai.GenerativeModel(MODEL_TEXT)
        response = model.generate_content(question)
        user_history[chat_id]["questions"].append(question)
        bot.send_message(chat_id, f"🤖 Ответ:\n{response.text}", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка: {e}", reply_markup=main_menu())


# ======== Flask сервер ========
@app.route("/", methods=["GET"])
def index():
    return "🤖 Telegram бот запущен на Render!", 200


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200


# ======== Запуск ========
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

