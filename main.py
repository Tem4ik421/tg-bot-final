import os
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import requests
import feedparser

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
user_history = {}

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль")
    markup.row("🖼️ Генератор Медиа", "⚓ Морские новости")
    markup.row("🎨 Создать презентацию", "❓ Ответы на вопросы")
    return markup

@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_history.setdefault(chat_id, {"questions": [], "media": [], "presentations": [], "news": []})
    bot.send_message(chat_id,
                     f"Привет, {message.from_user.first_name}! 👋\nВыбери опцию из меню:",
                     reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    chat_id = message.chat.id
    hist = user_history.get(chat_id, {})
    txt = (f"<b>Твой профиль</b>\n"
           f"ID: <code>{chat_id}</code>\n"
           f"Username: @{message.from_user.username}\n"
           f"Дата: {datetime.now().strftime('%Y-%m-%d')}\n\n"
           f"Вопросов: {len(hist['questions'])}\n"
           f"Медиа: {len(hist['media'])}\n"
           f"Презентаций: {len(hist['presentations'])}\n"
           f"Новостей: {len(hist['news'])}")
    bot.send_message(chat_id, txt, reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Фото", "🎬 Видео")
    markup.row("⬅️ Назад в меню")
    bot.send_message(message.chat.id, "Выберите тип медиа:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["📸 Фото", "🎬 Видео"])
def media_generate(message):
    chat_id = message.chat.id
    kind = "фото" if "Фото" in message.text else "видео"
    bot.send_message(chat_id, f"🔄 Генерирую {kind}... (это может занять пару секунд)")
    user_history[chat_id]["media"].append(kind)
    bot.send_message(chat_id, f"✅ {kind.capitalize()} готово! (тут будет настоящее медиа)",
                     reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def presentation(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🎨 Создаю презентацию в журнальном стиле...")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 18)
    pdf.multi_cell(0, 10, "📰 Презентация в журнальном стиле\n\nЭто пример оформления.")
    fname = f"presentation_{chat_id}.pdf"
    pdf.output(fname)
    user_history[chat_id]["presentations"].append(fname)
    bot.send_document(chat_id, open(fname, "rb"), reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🌊 Получаю морские новости...")
    rss = feedparser.parse("https://news.un.org/feed/subscribe/ru/news/topic/sea/feed/rss.xml")
    for e in rss.entries[:3]:
        txt = f"<b>{e.title}</b>\n{e.link}"
        bot.send_message(chat_id, txt)
    user_history[chat_id]["news"].append(datetime.now())

@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def faq(message):
    bot.send_message(message.chat.id, "Задай свой вопрос, я отвечу максимально подробно!")

@bot.message_handler(func=lambda m: m.text not in ["⬅️ Назад в меню"])
def handle_q(message):
    chat_id = message.chat.id
    user_history[chat_id]["questions"].append(message.text)
    bot.send_message(chat_id, f"💬 Ты спросил: <i>{message.text}</i>\n\n(Позже добавим ответы через Gemini)",
                     reply_markup=main_menu())

print("✅ Бот запущен и готов к работе.")
bot.polling()


