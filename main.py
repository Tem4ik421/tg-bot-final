import os
import telebot
from telebot import types
import datetime
from io import BytesIO
from PIL import Image
import requests
import feedparser
from weasyprint import HTML
import google.generativeai as genai
import time

# ======================
# 1️⃣ Ключи и API
# ======================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

if not TOKEN or not GEMINI_API_KEY:
    print("Не найдены ключи TELEGRAM_BOT_TOKEN или GEMINI_API_KEY")
    exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
genai.configure(api_key=GEMINI_API_KEY)

# ======================
# 2️⃣ История действий
# ======================
user_history = {}

def add_history(user_id, action, detail=""):
    if user_id not in user_history:
        user_history[user_id] = {"actions": [], "questions": []}
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_history[user_id]["actions"].append(f"[{timestamp}] {action}: {detail}")

def add_question(user_id, question):
    if user_id not in user_history:
        user_history[user_id] = {"actions": [], "questions": []}
    user_history[user_id]["questions"].append(question)

# ======================
# 3️⃣ Главное меню
# ======================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    profile_btn = types.KeyboardButton("👤 Профиль")
    media_btn = types.KeyboardButton("🖼️ Генератор Медиа")
    news_btn = types.KeyboardButton("⚓ Морские новости")
    presentation_btn = types.KeyboardButton("🎨 Создать презентацию")
    faq_btn = types.KeyboardButton("❓ Ответы на вопросы")
    markup.add(profile_btn)
    markup.add(media_btn, news_btn)
    markup.add(presentation_btn, faq_btn)
    return markup

# ======================
# 4️⃣ /start
# ======================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "Привет! Я готов к работе. Выбери опцию из меню:",
        reply_markup=main_menu()
    )
    add_history(message.from_user.id, "Запуск бота")

# ======================
# 5️⃣ Профиль
# ======================
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user_id = message.from_user.id
    username = message.from_user.username
    date_now = datetime.datetime.now().strftime("%Y-%m-%d")
    actions = user_history.get(user_id, {}).get("actions", [])
    questions = user_history.get(user_id, {}).get("questions", [])

    text = f"ID: {user_id}\nUsername: @{username}\nДата: {date_now}\n\nПоследние действия:"
    for a in actions[-5:]:
        text += f"\n{a}"
    text += f"\n\nЗадано вопросов: {len(questions)}"

    markup = types.InlineKeyboardMarkup()
    if questions:
        markup.add(types.InlineKeyboardButton("Показать все вопросы", callback_data="show_questions"))
    bot.send_message(message.chat.id, text, reply_markup=markup)
    add_history(user_id, "Открыт профиль")

@bot.callback_query_handler(func=lambda c: c.data == "show_questions")
def show_questions(c):
    user_id = c.from_user.id
    questions = user_history.get(user_id, {}).get("questions", [])
    text = "\n".join(questions) if questions else "Вопросов нет."
    bot.send_message(c.message.chat.id, f"Все ваши вопросы:\n{text}")

# ======================
# 6️⃣ Генератор Медиа
# ======================
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    photo_btn = types.KeyboardButton("Фото")
    video_btn = types.KeyboardButton("Видео")
    back_btn = types.KeyboardButton("Назад в главное меню")
    markup.add(photo_btn, video_btn)
    markup.add(back_btn)
    bot.send_message(message.chat.id, "Выберите тип генерации:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Видео"])
def generate_media(message):
    user_id = message.from_user.id
    msg = bot.send_message(message.chat.id, f"Введите описание для {message.text.lower()}:")
    bot.register_next_step_handler(msg, lambda m: process_media(m, message.text))

def process_media(message, media_type):
    user_id = message.from_user.id
    prompt = message.text
    add_history(user_id, f"Генерация {media_type}", prompt)
    add_question(user_id, prompt)

    # Анимация прогресса
    status_msg = bot.send_message(message.chat.id, f"Генерация {media_type}... ⏳")
    for i in range(3):
        bot.edit_message_text(f"Генерация {media_type}... {'•'*(i+1)}", message.chat.id, status_msg.message_id)
        time.sleep(1)

    if media_type == "Фото":
        result = genai.images.generate(prompt=prompt, size="1024x1024")
        img_url = result.data[0].url
        bot.send_photo(message.chat.id, img_url)
    else:
        bot.send_message(message.chat.id, f"Видео по запросу '{prompt}' сгенерировано! (реальный видеопоток интегрируется)")

# ======================
# 7️⃣ Создание презентации
# ======================
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def create_presentation(message):
    user_id = message.from_user.id
    bot.send_message(message.chat.id, "Генерация PDF-презентации...")
    add_history(user_id, "Создание презентации")

    html_content = """
    <h1 style="text-align:center;">Презентация</h1>
    <p style="text-align:justify;">Пример PDF с текстом и картинками.</p>
    <img src="https://source.unsplash.com/800x400/?nature" style="width:100%;"/>
    """
    pdf_file = BytesIO()
    HTML(string=html_content).write_pdf(pdf_file)
    pdf_file.seek(0)
    bot.send_document(message.chat.id, pdf_file, "presentation.pdf")

# ======================
# 8️⃣ Морские новости
# ======================
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    user_id = message.from_user.id
    add_history(user_id, "Морские новости")
    feed_url = "https://www.maritime-executive.com/rss/news"
    feed = feedparser.parse(feed_url)
    news = feed.entries[:3]

    for entry in news:
        text = f"{entry.title}\n{entry.link}\n"
        if hasattr(entry, 'summary'):
            text += entry.summary
        bot.send_message(message.chat.id, text)

# ======================
# 9️⃣ Ответы на вопросы
# ======================
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def ask_question(message):
    user_id = message.from_user.id
    msg = bot.send_message(message.chat.id, "Задайте вопрос:")
    bot.register_next_step_handler(msg, process_question)

def process_question(message):
    user_id = message.from_user.id
    question = message.text
    add_history(user_id, "Вопрос", question)
    add_question(user_id, question)
    bot.send_message(message.chat.id, f"Ищем ответ на: {question}... ⏳")
    response = genai.generate_text(model="models/text-bison-001", prompt=question)
    bot.send_message(message.chat.id, response.result)

# ======================
# 10️⃣ Назад в главное меню
# ======================
@bot.message_handler(func=lambda m: m.text == "Назад в главное меню")
def back_to_main(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())

# ======================
# 11️⃣ Запуск бота
# ======================
print("Бот запущен. Ожидание сообщений...")
bot.polling(none_stop=True)

