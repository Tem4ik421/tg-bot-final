import os
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import feedparser

# ======== Ключи из переменных окружения ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # пример: https://tg-bot-final.onrender.com
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# ======== Инициализация ========
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ======== Хранилище действий ========
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
    bot.send_message(
        chat_id,
        f"Привет, {message.from_user.first_name}! 👋\nВыбери опцию из меню:",
        reply_markup=main_menu()
    )

# ======== Профиль ========
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    chat_id = message.chat.id
    hist = user_history.get(chat_id, {"questions": [], "media": [], "presentations": [], "news": []})
    text = (
        f"<b>Твой профиль</b>\n"
        f"ID: <code>{chat_id}</code>\n"
        f"Username: @{message.from_user.username or 'не указан'}\n"
        f"Дата: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"📊 Вопросов: {len(hist['questions'])}\n"
        f"🖼️ Медиа: {len(hist['media'])}\n"
        f"📘 Презентаций: {len(hist['presentations'])}\n"
        f"⚓ Новостей: {len(hist['news'])}"
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📄 История действий", "⬅️ Назад в меню")
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📄 История действий")
def show_history(message):
    chat_id = message.chat.id
    hist = user_history.get(chat_id, {})
    text = "🧾 <b>История действий:</b>\n"
    for k, v in hist.items():
        text += f"\n• {k.capitalize()}: {len(v)}"
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
    bot.send_message(chat_id, f"🔄 Генерирую {kind}... Пожалуйста, подождите 🕓")
    # Заглушка — позже можно подключить Gemini API
    user_history[chat_id]["media"].append(kind)
    bot.send_message(chat_id, f"✅ {kind.capitalize()} готово! (здесь будет настоящее {kind})", reply_markup=main_menu())

# ======== Презентация ========
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🎨 Создаю презентацию в журнальном стиле...")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.multi_cell(0, 10, "📰 Презентация в журнальном стиле\n\nПример оформления с заголовками и текстом.")
    filename = f"presentation_{chat_id}.pdf"
    pdf.output(filename)
    user_history[chat_id]["presentations"].append(filename)
    bot.send_document(chat_id, open(filename, "rb"), reply_markup=main_menu())

# ======== Морские новости ========
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🌊 Получаю актуальные морские новости...")
    feed = feedparser.parse("https://news.un.org/feed/subscribe/ru/news/topic/sea/feed/rss.xml")
    for e in feed.entries[:3]:
        text = f"<b>{e.title}</b>\n{e.link}"
        bot.send_message(chat_id, text)
    user_history[chat_id]["news"].append(datetime.now())

# ======== Ответы на вопросы ========
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def question_start(message):
    bot.send_message(message.chat.id, "💬 Задай любой вопрос, и я постараюсь ответить!")

@bot.message_handler(func=lambda m: m.text not in ["⬅️ Назад в меню"])
def answer_question(message):
    chat_id = message.chat.id
    user_history[chat_id]["questions"].append(message.text)
    bot.send_message(chat_id, f"🤖 Ты спросил: {message.text}\n(Позже добавим реальный ответ через Gemini)", reply_markup=main_menu())

# ======== Flask веб-сервер ========
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

    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Запуск Flask на порту {port}...")
    app.run(host="0.0.0.0", port=port)


