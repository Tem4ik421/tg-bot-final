# -*- coding: utf-8 -*-
import os
import time
import threading
import base64
import requests
import re
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
from fpdf import FPDF
import google.generativeai as genai
from io import BytesIO

# ======== 🔐 Ключи и модели ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") or "https://tg-bot-final-1.onrender.com"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Модели
MODEL_TEXT = "models/gemini-2.5-pro"
MODEL_IMAGE = "models/imagen-3"

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ======== 🗃️ Хранилище ========
user_history = {}
# Словарь для управления анимациями загрузки
loading_messages = {}

# ======== 💤 Антифриз (Render ping) ========
def keep_alive():
    while True:
        try:
            requests.get(WEBHOOK_HOST)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💤 Ping → Render OK")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Ping Error: {e}")
        time.sleep(600) # 10 минут

threading.Thread(target=keep_alive, daemon=True).start()

# ======== 🔄 Анимация загрузки ========
def animate_loading(chat_id, message_id, text):
    """Анимирует сообщение о загрузке."""
    dots = ""
    while loading_messages.get(chat_id) == message_id:
        try:
            dots = "." * (len(dots) % 3 + 1)
            bot.edit_message_text(f"{text}{dots}", chat_id, message_id)
            time.sleep(0.7)
        except Exception as e:
            if "message to edit not found" in str(e):
                break
            print(f"Ошибка анимации: {e}")
            time.sleep(2)

def start_loading_animation(chat_id, text):
    """Отправляет сообщение о загрузке и запускает анимацию."""
    try:
        msg = bot.send_message(chat_id, text + "...")
        loading_messages[chat_id] = msg.message_id
        threading.Thread(target=animate_loading, args=(chat_id, msg.message_id, text), daemon=True).start()
        return msg
    except Exception as e:
        print(f"Ошибка старта анимации: {e}")
        return None

def stop_loading_animation(chat_id, message_id):
    """Останавливает анимацию и удаляет сообщение."""
    if loading_messages.get(chat_id) == message_id:
        loading_messages.pop(chat_id, None)
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Ошибка остановки анимации: {e}")

# -------------------------------------------------------------------
# ✅ ФУНКЦИЯ "НАРЕЗКИ" СООБЩЕНИЙ (из прошлого раза)
# -------------------------------------------------------------------
def send_long_message(chat_id, text, **kwargs):
    """
    Отправляет длинное сообщение, разбивая его на части по 4096 символов.
    """
    if len(text) <= 4096:
        bot.send_message(chat_id, text, **kwargs)
        return

    parts = []
    while len(text) > 0:
        if len(text) > 4096:
            part = text[:4096]
            # Пытаемся найти последний перенос строки, чтобы не рвать слово
            last_newline = part.rfind('\n')
            if last_newline != -1:
                parts.append(text[:last_newline])
                text = text[last_newline + 1:]
            else:
                # Если переносов нет, рвем по 4096
                parts.append(part)
                text = text[4096:]
        else:
            parts.append(text)
            text = ""

    for part in parts:
        bot.send_message(chat_id, part, **kwargs)
        time.sleep(0.5) 

# ========  menus Главное меню ========
def main_menu():
    """Возвращает Reply-клавиатуру главного меню."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль")
    markup.row("🖼️ Генератор Медиа", "⚓ Морские новости")
    markup.row("🎨 Создать презентацию", "❓ Ответы на вопросы")
    return markup

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat_id
    user_history.setdefault(chat_id, {
        "questions": [],
        "media": [],
        "presentations": [],
        "news": []
    })
    # -------------------------------------------------------------------
    # ✅ ИЗМЕНЕНИЕ ДЛЯ ТЕСТА
    # -------------------------------------------------------------------
    bot.send_message(
        chat_id,
        f"--- DEBUG-TEST-1 --- Привет, {message.from_user.first_name}! 👋\nЯ твой ассистент на базе Gemini. Выбери опцию:", 
        reply_markup=main_menu()
    )

# ======== 👤 Профиль ========
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    chat_id = message.chat.id
    hist = user_history.get(chat_id, {
        "questions": [], "media": [], "presentations": [], "news": []
    })

    text = (
        f"<b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{chat_id}</code>\n"
        f"👤 Username: @{message.from_user.username or 'Не указан'}\n"
        f"📅 Дата: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"<b>📊 Твоя активность:</b>\n"
        f"  ❓ Вопросов задано: {len(hist['questions'])}\n"
        f"  🖼️ Медиа создано: {len(hist['media'])}\n"
        f"  📘 Презентаций: {len(hist['presentations'])}\n"
        f"  ⚓ Новостей просмотрено: {len(hist['news'])}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Показать вопросы", callback_data="history_questions"),
        types.InlineKeyboardButton("Показать медиа", callback_data="history_media")
    )
    markup.row(
        types.InlineKeyboardButton("Показать презентации", callback_data="history_presentations"),
        types.InlineKeyboardButton("Показать новости", callback_data="history_news")
    )

    bot.send_message(chat_id, text, reply_markup=markup)

# --- Обработчик кнопок профиля ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('history_'))
def handle_history_callback(call):
    chat_id = call.message.chat.id
    category = call.data.split('_')[1]
    hist_list = user_history.get(chat_id, {}).get(category, [])
    
    if not hist_list:
        bot.answer_callback_query(call.id, "📭 В этой категории история пуста.", show_alert=True)
        return

    titles = {
        "questions": "❓ Твои вопросы:",
        "media": "🖼️ Твои медиа-запросы:",
        "presentations": "📘 Твои презентации:",
        "news": "⚓ Просмотренные новости (по датам):"
    }
    title = titles.get(category, "📜 Твоя история:")
    formatted_list = [f"• <code>{item}</code>" for item in hist_list[-10:]]
    text = f"<b>{title}</b> (последние 10):\n\n" + "\n".join(formatted_list)
    
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, text)

# ======== 🖼️ Генератор медиа ========
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медиа")
def media_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("📸 Фото", "🎬 Видео (в разработке)")
    markup.row("⬅️ Назад в меню")
    bot.send_message(message.chat.id, "Выберите тип медиа:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад в меню")
def back_to_main_menu(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == "📸 Фото")
def ask_image_prompt(message):
    msg_text = (
        "✏️ Введите описание (промпт) для генерации изображения.\n\n"
        "<b>На русском:</b>\n"
        "<i>«кот в скафандре на Марсе, фотореализм»</i>\n\n"
        "<b>На английском (часто дает лучший результат):</b>\n"
        "<i>«a cat in an astronaut suit on Mars, photorealistic»</i>"
    )
    msg = bot.send_message(message.chat.id, msg_text, reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, generate_image)

def generate_image(message):
    """Основная функция генерации изображения по запросу пользователя."""
    chat_id = message.chat.id
    prompt = message.text

    if prompt == "⬅️ Назад в меню":
        back_to_main_menu(message)
        return

    loading = start_loading_animation(chat_id, "🔄 Генерирую фото через Imagen 3")

    try:
        image_bytes = generate_image_bytes(prompt) 
        if not image_bytes:
            raise ValueError("Не удалось сгенерировать изображение (пустой ответ от API).")

        user_history[chat_id]["media"].append(prompt)
        print(f"📸 Изображение сгенерировано для {chat_id}: {prompt}")

        stop_loading_animation(chat_id, loading.message_id)
        bot.send_photo(chat_id, image_bytes, caption=f"🖼️ Ваш запрос: <i>{prompt}</i>")

    except Exception as e:
        if loading:
            stop_loading_animation(chat_id, loading.message_id)
        # -------------------------------------------------------------------
        # ✅ ИСПРАВЛЕНИЕ #1 (Обрезаем ошибку)
        # -------------------------------------------------------------------
        bot.send_message(chat_id, f"❌ Ошибка при генерации изображения: {str(e)[:1000]}")

    bot.send_message(chat_id, "Что делаем дальше?", reply_markup=main_menu())

# (Функция generate_image_bytes)
def generate_image_bytes(prompt: str) -> bytes | None:
    """Генерация изображения через Imagen (официальный endpoint v1)."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL_IMAGE}:predict?key={GEMINI_API_KEY}"
        payload = {
            "instances": [
                {
                    "prompt": {"text": prompt},
                    "parameters": {
                        "sampleCount": 1,
                        "aspectRatio": "1:1",
                        "safetyFilterLevel": "block_none" 
                    }
                }
            ]
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if "predictions" not in data or not data["predictions"]:
            print(f"Ошибка Imagen API: {data}") 
            return None

        image_base64 = data["predictions"][0]["bytesBase64Encoded"]
        return base64.b64decode(image_base64)

    except Exception as e:
        print(f"Критическая ошибка generate_image_bytes: {e}")
        return None

# ======== ⚓ Морские новости ========
@bot.message_handler(func=lambda m: m.text == "⚓ Морские новости")
def maritime_news(message):
    chat_id = message.chat.id
    loading = start_loading_animation(chat_id, "🌊 Ищу актуальные морские новости")

    try:
        model = genai.GenerativeModel(MODEL_TEXT)
        prompt = (
            "Найди 3 самые свежие и важные морские новости (за последние 48 часов). "
            "Для каждой новости предоставь:\n"
            "1. 📰 *Заголовок* (жирным)\n"
            "2. 📝 *Сводку* (2-3 предложения)\n"
            "3. 🔗 *Прямую ссылку (URL)* на источник.\n"
            "4. 📸 (Если найдешь) *Ссылку (URL) на релевантное изображение*.\n"
            "5. 🎬 (Если найдешь) *Ссылку (URL) на YouTube видео* по теме.\n\n"
            "Отформатируй ответ красиво для Telegram (используй Markdown или HTML)."
        )

        response = model.generate_content(prompt)
        stop_loading_animation(chat_id, loading.message_id)

        if response.text:
            # -------------------------------------------------------------------
            # ✅ ИСПРАВЛЕНИЕ #2 (Используем "нарезку")
            # -------------------------------------------------------------------
            send_long_message(chat_id, response.text, disable_web_page_preview=True)
        else:
            bot.send_message(chat_id, "❌ Не удалось получить новости.")

    except Exception as e:
        if loading:
            stop_loading_animation(chat_id, loading.message_id)
        # -------------------------------------------------------------------
        # ✅ ИСПРАВЛЕНИЕ #3 (Обрезаем ошибку)
        # -------------------------------------------------------------------
        bot.send_message(chat_id, f"⚠️ Ошибка при получении новостей: {str(e)[:1000]}") 

# ======== 🎨 Презентации ========
@bot.message_handler(func=lambda m: m.text == "🎨 Создать презентацию")
def ask_presentation_topic(message):
    msg = bot.send_message(message.chat.id, "📘 Введите тему для презентации (например: «История пиратства» или «Современные танкеры»):", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, generate_presentation)

def generate_presentation(message):
    chat_id = message.chat.id
    topic = message.text

    if topic == "⬅️ Назад в меню":
        back_to_main_menu(message)
        return

    loading_msg = None
    try:
        loading_msg = start_loading_animation(chat_id, f"🎨 Придумываю презентацию на тему «{topic}»")
        user_history[chat_id]["presentations"].append(topic)

        # 1. Генерируем текст
        text_model = genai.GenerativeModel(MODEL_TEXT)
        prompt = f"""
        Создай контент для 5-слайдовой презентации в журнальном стиле на тему '{topic}'.
        
        Структура должна быть следующей (строго соблюдай формат):
        
        [TITLE]
        Заголовок презентации
        
        [SLIDE_1]
        [IMAGE_PROMPT: <очень подробный, фотореалистичный англ. промпт для обложки>]
        [HEADER: <Заголовок слайда 1 (Введение)>]
        [TEXT: <2-3 абзаца текста для слайда 1>]
        
        [SLIDE_2]
        [IMAGE_PROMPT: <подробный фотореалистичный англ. промпт для слайда 2>]
        [HEADER: <Заголовок слайда 2>]
        [TEXT: <2-3 абзаца текста для слайда 2>]

        [SLIDE_3]
        [IMAGE_PROMPT: <подробный фотореалистичный англ. промпт для слайда 3>]
        [HEADER: <Заголовок слайда 3>]
        [TEXT: <2-3 абзаца текста для слайда 3>]

        [SLIDE_4]
        [IMAGE_PROMPT: <подробный фотореалистичный англ. промпт для слайда 4>]
        [HEADER: <Заголовок слайда 4 (Заключение)>]
        [TEXT: <2-3 абзаца текста для слайда 4>]
        """

        text_response = text_model.generate_content(prompt).text

        title = (re.search(r"\[TITLE\]\n(.*?)\n\n\[SLIDE_1\]", text_response, re.DOTALL) or [None, "Презентация"])[1].strip()
        slides_content = re.findall(r"\[IMAGE_PROMPT: (.*?)\]\n\[HEADER: (.*?)\]\n\[TEXT: (.*?)\](?=\n\n\[SLIDE_|\Z)", text_response, re.DOTALL)

        if not slides_content:
            raise ValueError("Gemini вернул текст в неверном формате. Не могу распарсить.")

        # 3. Генерируем изображения
        bot.edit_message_text(f"🖼️ Генерирую {len(slides_content)} изображений...", chat_id, loading_msg.message_id)

        images = []
        for img_prompt, _, _ in slides_content:
            img_bytes = generate_image_bytes(img_prompt.strip())
            if img_bytes:
                images.append(BytesIO(img_bytes))
            else:
                images.append(None)

        # 4. Собираем PDF
        bot.edit_message_text("✍️ Собираю PDF-документ...", chat_id, loading_msg.message_id)

        pdf = FPDF()

        try:
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
            font = 'DejaVu'
        except RuntimeError:
            print("ВНИМАНИЕ: Шрифты DejaVu не найдены. Использую Arial (кириллица не будет работать).")
            font = 'Arial'

        # --- Титульный слайд ---
        pdf.add_page()
        pdf.set_font(font, 'B', 24)
        pdf.multi_cell(0, 15, f"\n{title}", align='C')
        pdf.set_font(font, '', 14)
        pdf.multi_cell(0, 10, f"\nТема: {topic}", align='C')
        if images[0]:
            img_w, img_h = 180, 120
            x_pos = (210 - img_w) / 2
            y_pos = pdf.get_y() + 10
            img_path = f"temp_cover_{chat_id}.png"
            with open(img_path, 'wb') as f:
                f.write(images[0].getvalue())
            pdf.image(img_path, x=x_pos, y=y_pos, w=img_w)
            os.remove(img_path)

        # --- Слайды с контентом ---
        for i, (img_prompt, header, text) in enumerate(slides_content):
            if i == 0: continue

            pdf.add_page()

            if images[i]:
                img_path = f"temp_img_{chat_id}_{i}.png"
                with open(img_path, 'wb') as f:
                    f.write(images[i].getvalue())

                img_w, img_h = 190, 95
                x_pos = (210 - img_w) / 2
                pdf.image(img_path, x=x_pos, y=10, w=img_w)
                os.remove(img_path)
                pdf.ln(img_h + 5)
            else:
                pdf.ln(10)

            pdf.set_font(font, 'B', 18)
            pdf.multi_cell(0, 10, header.strip(), align='C')
            pdf.ln(5)

            pdf.set_font(font, '', 12)
            pdf.multi_cell(0, 8, text.strip())

        # 5. Отправляем PDF
        filename = f"presentation_{chat_id}_{topic.replace(' ','_')[:15]}.pdf"
        pdf_bytes = pdf.output(dest='S').encode('latin-1')

        stop_loading_animation(chat_id, loading_msg.message_id)

        bot.send_document(chat_id, BytesIO(pdf_bytes), visible_file_name=filename)
        print(f"📘 PDF готов для {chat_id}")

    except Exception as e:
        if loading_msg:
            stop_loading_animation(chat_id, loading_msg.message_id)
        # -------------------------------------------------------------------
        # ✅ ИСПРАВЛЕНИЕ #4 (Обрезаем ошибку)
        # -------------------------------------------------------------------
        bot.send_message(chat_id, f"⚠️ Ошибка при создании презентации: {str(e)[:1000]}")

    bot.send_message(chat_id, "Что делаем дальше?", reply_markup=main_menu())


# ======== ❓ Вопросы ========
@bot.message_handler(func=lambda m: m.text == "❓ Ответы на вопросы")
def ask_question(message):
    msg_text = (
        "💬 Задай любой вопрос — я отвечу через Gemini 2.5 Pro.\n\n" 
        "<i>Например: «расскажи про будущее AI» или «что такое МАРПОЛ?»</i>"
    )
    msg = bot.send_message(message.chat.id, msg_text, reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, answer_question)

def answer_question(message):
    chat_id = message.chat.id
    question = message.text

    if question == "⬅️ Назад в меню":
        back_to_main_menu(message)
        return

    loading = start_loading_animation(chat_id, "🤔 Думаю над ответом")

    try:
        img_thread = threading.Thread(target=generate_image_helper, args=(chat_id, question), daemon=True)
        img_thread.start()

        model = genai.GenerativeModel(MODEL_TEXT)
        prompt = (
            f"Ответь на вопрос пользователя: «{question}».\n\n"
            "Твой ответ должен быть подробным и четким. "
            "Также, пожалуйста, НАЙДИ В ИНТЕРНЕТЕ и включи в свой ответ:\n"
            "1. (Если релевантно) 1-2 ссылки (URL) на надежные источники (статьи).\n"
            "2. (Если релевантно) 1 ссылку (URL) на YouTube видео по теме."
        )

        response = model.generate_content(prompt)
        user_history[chat_id]["questions"].append(question)

        img_thread.join(timeout=15)

        stop_loading_animation(chat_id, loading.message_id)

        if response.text:
            # -------------------------------------------------------------------
            # ✅ ИСПРАВЛЕНИЕ #5 (Используем "нарезку")
            # -------------------------------------------------------------------
            send_long_message(chat_id, response.text, disable_web_page_preview=False)
        else:
            bot.send_message(chat_id, "❌ Не удалось получить текстовый ответ.")

    except Exception as e:
        if loading:
            stop_loading_animation(chat_id, loading.message_id)
        # -------------------------------------------------------------------
        # ✅ ИСПРАВЛЕНИЕ #6 (Обрезаем ошибку)
        # -------------------------------------------------------------------
        bot.send_message(chat_id, f"⚠️ Ошибка при ответе: {str(e)[:1000]}")

    bot.send_message(chat_id, "Что делаем дальше?", reply_markup=main_menu())

def generate_image_helper(chat_id, prompt):
    """Хелпер: генерирует и сразу отправляет фото (для Q&A)."""
    try:
        model = genai.GenerativeModel(MODEL_TEXT) 
        img_prompt_gen = model.generate_content(
            f"Создай один короткий, фотореалистичный промпт на английском для генерации изображения по теме: «{prompt}»"
        )
        img_prompt = img_prompt_gen.text.strip()

        image_bytes = generate_image_bytes(img_prompt)
        if image_bytes:
            bot.send_photo(chat_id, image_bytes)
    except Exception as e:
        print(f"Ошибка в generate_image_helper: {e}")

# ======== 🌍 Flask сервер ========
@app.route("/", methods=["GET"])
def index():
    return "🤖 Бот работает на Render! (Gemini Edition)", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return "ok", 200
    else:
        return "Unsupported Media Type", 415

# ======== 🚀 Запуск ========
if __name__ == "__main__":
    print("Бот запускается...")
    try:
        bot.remove_webhook()
        time.sleep(0.5)
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Вебхук установлен: {WEBHOOK_URL}")

        port = int(os.getenv("PORT", 5000))
        app.run(host="0.0.0.0", port=port)

    except Exception as e:
        print(f"❌ Ошибка при установке вебхука или запуске Flask: {e}")
