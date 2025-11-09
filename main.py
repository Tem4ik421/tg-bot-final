import os
import telebot
from flask import Flask, request
from datetime import datetime
import feedparser
from weasyprint import HTML
from io import BytesIO
from PIL import Image
import requests
import google.generativeai as genai

# --- Получение ключей из Environment Variables ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST")
PORT = int(os.environ.get("PORT", 5000))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

WEBHOOK_URL_PATH = f"/{TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_URL_PATH}"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# --- Инициализация Gemini ---
genai.configure(api_key=GEMINI_API_KEY)

# --- Журнал действий пользователя ---
user_actions = {}  # {user_id: [{"action": "question", "text": "..."}, ...]}

# --- Главное меню ---
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("👤 Профиль"))
    markup.row(KeyboardButton("🖼️ Генератор Медиа"), KeyboardButton("⚓ Морские новости"))
    markup.row(KeyboardButton("🎨 Создать презентацию"), KeyboardButton("❓ Ответы на вопросы"))
    return markup

# --- Профиль ---
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user_id = message.from_user.id
    username = message.from_user.username
    date = datetime.now().strftime("%Y-%m-%d")
    actions = user_actions.get(user_id, [])
    text = f"ID: {user_id}\nUsername: @{username}\nДата: {date}\n\nДействия с ботом: {len(actions)}\n"
    text += "Нажми /history чтобы увидеть все вопросы и действия."
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(commands=["history"])
def history(message):
    user_id = message.from_user.id
    actions = user_actions.get(user_id, [])
    if not actions:
        bot.send_message(message.chat.id, "История пустая.", reply_markup=main_menu())
        return
    text = "История действий:\n"
    for i, a in enumerate(actions[-20:], 1):
        text += f"{i}. {a['action']}: {a['text']}\n"
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

# --- Генератор медиа ---
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("Фото"), KeyboardButton("Видео"))
    markup.row(KeyboardButton("Назад в главное меню"))
    bot.send_message(message.chat.id, "Выберите тип генерации:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Видео"])
def generate_media(message):
    prompt = bot.send_message(message.chat.id, "Введите описание для генерации:")
    bot.register_next_step_handler(prompt, do_generate_media, message.text)

def do_generate_media(message, media_type):
    user_id = message.from_user.id
    text_prompt = message.text
    user_actions.setdefault(user_id, []).append({"action": f"generate {media_type}", "text": text_prompt})

    bot.send_message(message.chat.id, f"Генерация {media_type} по запросу: {text_prompt} ...")
    if media_type == "Фото":
        image_url = f"https://source.unsplash.com/600x400/?{text_prompt.replace(' ', '%20')}"
        bot.send_photo(message.chat.id, photo=image_url)
    else:
        bot.send_message(message.chat.id, f"Видео с промптом '{text_prompt}' сгенерировано (пример).")

    bot.send_message(message.chat.id, "Готово!", reply_markup=main_menu())

# --- Создать презентацию ---
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(message):
    user_id = message.from_user.id
    user_actions.setdefault(user_id, []).append({"action": "create_presentation", "text": "PDF"})
    
    html_content = f"""
    <h1>Презентация для @{message.from_user.username}</h1>
    <p>Дата: {datetime.now().strftime('%Y-%m-%d')}</p>
    <p>Пример контента с изображением:</p>
    <img src='https://source.unsplash.com/400x200/?nature' width='400'/>
    """
    pdf_file = BytesIO()
    HTML(string=html_content).write_pdf(pdf_file)
    pdf_file.seek(0)
    bot.send_document(message.chat.id, ("presentation.pdf", pdf_file), reply_markup=main_menu())

# --- Морские новости ---
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    # Пример с RSS
    feed = feedparser.parse("https://www.maritime-executive.com/rss.xml")
    user_id = message.from_user.id
    user_actions.setdefault(user_id, []).append({"action": "maritime_news", "text": "latest news"})
    text = "Актуальные морские новости:\n"
    for entry in feed.entries[:5]:
        text += f"- <a href='{entry.link}'>{entry.title}</a>\n"
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=main_menu())

# --- Ответы на вопросы ---
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def ask_question(message):
    user_id = message.from_user.id
    user_actions.setdefault(user_id, []).append({"action": "ask_question", "text": ""})
    bot.send_message(message.chat.id, "Задайте вопрос (текст):", reply_markup=main_menu())
    bot.register_next_step_handler(message, answer_question)

def answer_question(message):
    user_id = message.from_user.id
    user_actions.setdefault(user_id, []).append({"action": "answered_question", "text": message.text})
    bot.send_message(message.chat.id, f"Вы спросили: {message.text}\nОтвет сгенерирован (пример).", reply_markup=main_menu())

# --- Назад в главное меню ---
@bot.message_handler(func=lambda m: m.text == "Назад в главное меню")
def back_to_main(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())

# --- Webhook ---
@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=['GET'])
def index():
    return "Бот работает!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=PORT)

