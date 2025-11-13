# -*- coding: utf-8 -*-
import os
import time
import threading
import requests
import json
import re
import base64
from flask import Flask, request
import telebot
from telebot import types
from fpdf import FPDF
from io import BytesIO
# -------------------------------------------------------------------
# ✅ ВИДАЛЕНО: Groq, Replicate
# ✅ ДОДАНО: google.generativeai
# -------------------------------------------------------------------
import google.generativeai as genai

# ======== КОНФІГ ========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GETIMG_API_KEY = os.getenv("GETIMG_API_KEY") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # <-- Використовуємо ключ Google

WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Ініціалізація
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        print("ПОПЕРЕДЖЕННЯ: GEMINI_API_KEY не знайдено.")
except Exception as e:
    print(f"Помилка конфігурації Gemini: {e}")

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

# ======== ПРОГРЕС-ПОЛОСКА ========
def progress_bar(percent, width=20):
    filled = int(width * percent // 100)
    bar = "█" * filled + "·" * (width - filled)
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
    k.row("👤 Профиль") 
    k.row("🖼️ Генератор Медіа", "⚓️ Морські новини")
    k.row("🎨 Створити презентацію", "❓ Відповіді на питання")
    return k

# -------------------------------------------------------------------
# ✅ ФУНКЦІЯ АВТО-ПЕРЕКЛАДУ (ПЕРЕВЕДЕНО НА GEMINI)
# -------------------------------------------------------------------
def translate_to_english(text_to_translate):
    """Перекладає текст на англійську, використовуючи Gemini."""
    if not GEMINI_API_KEY:
        print("Попередження: Gemini API не налаштований, переклад неможливий.")
        return text_to_translate 

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Translate the following text to English. Return ONLY the translated text, nothing else, no quotation marks: '{text_to_translate}'"
        response = model.generate_content(prompt)
        translated_text = response.text.strip().strip('"')
        
        if translated_text:
            print(f"Переклад (Gemini): '{text_to_translate}' -> '{translated_text}'")
            return translated_text
        else:
            return text_to_translate
    except Exception as e:
        print(f"Помилка перекладу (Gemini): {e}")
        return text_to_translate

# ======== ЗАХИСНА ФУНКЦІЯ ========
def ensure_user_data(cid):
    """Гарантує, що повна структура даних існує для користувача."""
    user_data.setdefault(cid, {})
    keys_to_init = ["questions", "media", "video", "pres", "news", "answers"]
    for key in keys_to_init:
        user_data[cid].setdefault(key, [])

# ======== /start ========
@bot.message_handler(commands=["start"])
def start(m):
    cid = m.chat.id
    ensure_user_data(cid) 
    bot.send_message(cid,
        "<b>КАПІТАН @Tem4ik4751 НА МОСТИКУ!</b>\n"
        "ID: <code>1474031301</code>\n"
        "Бот працює 24/7 — <b>СЛАВА ЗСУ!</b>\n\n"
        "<b>Обери функцію</b>",
        reply_markup=main_menu())

# ======== ПРОФІЛЬ ========
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):
    cid = m.chat.id
    ensure_user_data(cid) 
    u = user_data.get(cid)
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
    ensure_user_data(cid)
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
@bot.message_handler(func=lambda m: m.text == "🖼️ Генератор Медіа")
def media_menu(m):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("Фото", "Відео")
    k.row("Назад")
    bot.send_message(m.chat.id, "<b>ОБЕРИ ЗБРОЮ, КАПІТАНЕ!</b>", reply_markup=k)

@bot.message_handler(func=lambda m: m.text in ["Фото", "Відео"])
def ask_prompt(m):
    cid = m.chat.id
    
    if m.text == "Фото":
        media_type = "фото"
        example = "Кіт на даху, захід сонця, фотореализм"
        bot.send_message(cid,
            f"<b>ОПИШИ {media_type.upper()}:</b>\n"
            f"Приклад: <code>{example}</code>",
            reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(m, generate_photo)
    
    elif m.text == "Відео":
        # --- "ЗАГЛУШКА" для ВІДЕО ---
        placeholder_text = (
            "🎬 <b>Генерація Відео (в Розробці)</b>\n\n"
            "Капітане, ця функція ще будується на верфі! ⚓️\n\n"
            "Безкоштовних API для генерації відео не існує.\n\n"
            "А поки що, спробуй «Фото»!"
        )
        bot.send_message(cid, placeholder_text, reply_markup=main_menu())

# -------------------------------------------------------------------
# ✅ ФОТО (ПЕРЕВЕДЕНО НА GETIMG.AI - ЯКІСТЬ, АЛЕ З ФІЛЬТРОМ 18+)
# -------------------------------------------------------------------
def generate_photo(m):
    cid = m.chat.id
    prompt = m.text.strip().strip('«»"')
    
    ensure_user_data(cid) 
    user_data[cid]["media"].append(prompt)
    
    start_progress(cid, "ПЕРЕКЛАДАЮ (Gemini) ТА ГЕНЕРУЮ (Getimg.ai)") 

    if not GETIMG_API_KEY:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Getimg.ai API не налаштований.", reply_markup=main_menu())
        return

    try:
        translated_prompt = translate_to_english(prompt)
        
        url = "https://api.getimg.ai/v1/stable-diffusion/text-to-image"
        headers = {
            "Authorization": f"Bearer {GETIMG_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "stable-diffusion-xl-v1-0", # Якісна модель
            "prompt": translated_prompt,
            "negative_prompt": "Disfigured, cartoon, blurry, nude, nsfw, 18+", # Фільтр
            "width": 1024,
            "height": 1024,
            "steps": 30,
            "output_format": "jpeg"
        }

        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Помилка Getimg.ai: {response.status_code} - {response.text}")

        data = response.json()
        img_base64 = data.get("image")
        
        if not img_base64:
             raise Exception("Getimg.ai повернув порожню відповідь.")

        img_bytes = base64.b64decode(img_base64)
        
        stop_progress(cid)
        
        bot.send_photo(cid, img_bytes, caption=f"<b>ФОТО (Getimg.ai):</b> {prompt}", reply_markup=main_menu())

    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, f"[Error] Помилка Getimg.ai: {str(e)[:100]}", reply_markup=main_menu())


# -------------------------------------------------------------------
# ⚠️ ВІДЕО (ЗЛАМАНО)
# -------------------------------------------------------------------
def generate_video(m):
    cid = m.chat.id
    bot.send_message(cid, "Функція відео тимчасово недоступна.", reply_markup=main_menu())
    return 

# ======== НАЗАД ========
@bot.message_handler(func=lambda m: m.text == "Назад")
def back(m):
    bot.send_message(m.chat.id, "<b>ГОЛОВНЕ МЕНЮ</b>", reply_markup=main_menu())

# -------------------------------------------------------------------
# ✅ МОРСЬКІ НОВИНИ (ПЕРЕВЕДЕНО НА GEMINI)
# -------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "⚓️ Морські новини")
def news(m):
    cid = m.chat.id
    ensure_user_data(cid)
    start_progress(cid, "ШУКАЮ НОВИНИ (Gemini)")
    if not GEMINI_API_KEY:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Gemini API ключ не налаштований.", reply_markup=main_menu())
        return
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = "3 найцікавіші новини про океан за 24 год: заголовок, 2 речення, фото, відео YouTube, джерело. Markdown."
        
        response = model.generate_content(prompt)
        stop_progress(cid)
        bot.send_message(cid, response.text, disable_web_page_preview=False, reply_markup=main_menu())
        user_data[cid]["news"].append(time.strftime("%H:%M"))

    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, f"[Error] Помилка Gemini: {str(e)[:100]}", reply_markup=main_menu())

# -------------------------------------------------------------------
# ✅ ПРЕЗЕНТАЦІЇ: ДОПОМІЖНА ФУНКЦІЯ (Getimg.ai)
# -------------------------------------------------------------------
def generate_image_for_slide(prompt):
    """Допоміжна функція для генерації 1 зображення через Getimg.ai (повертає Bytes)."""
    if not GETIMG_API_KEY:
        print("Getimg.ai API не налаштований, зображення для слайду пропущено.")
        return None
        
    try:
        translated_prompt = translate_to_english(prompt)
        full_prompt = translated_prompt + ", professional, journal style, high resolution, minimalist"
        
        url = "https://api.getimg.ai/v1/stable-diffusion/text-to-image"
        headers = {
            "Authorization": f"Bearer {GETIMG_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "stable-diffusion-xl-v1-0",
            "prompt": full_prompt,
            "negative_prompt": "Disfigured, cartoon, blurry, nude, nsfw, 18+",
            "width": 1024, # 16:9
            "height": 576, # 16:9
            "steps": 25,
            "output_format": "jpeg"
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Помилка Getimg.ai (слайд): {response.status_code} - {response.text}")
        
        data = response.json()
        img_base64 = data.get("image")
        
        if img_base64:
            return base64.b64decode(img_base64)
        return None
        
    except Exception as e:
        print(f"Помилка генерації фото для слайду (Getimg.ai): {e}")
        return None

# -------------------------------------------------------------------
# ✅ ПРЕЗЕНТАЦІЯ (ПЕРЕВЕДЕНО НА GEMINI + GETIMG.AI)
# -------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🎨 Створити презентацію")
def create_pres(m):
    bot.send_message(m.chat.id, "<b>ТЕМА ПРЕЗЕНТАЦІЇ?</b>\nПриклад: <code>Майбутнє штучного інтелекту</code>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, gen_pres)

def gen_pres(m):
    cid = m.chat.id
    topic = m.text.strip()
    ensure_user_data(cid)
    user_data[cid]["pres"].append(topic) 
    
    loading_msg = start_progress(cid, f"1/3: Створюю план '{topic}' (Gemini)")
    
    if not GEMINI_API_KEY:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Gemini API ключ не налаштований.", reply_markup=main_menu())
        return
    if not GETIMG_API_KEY:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Getimg.ai API ключ не налаштований.", reply_markup=main_menu())
        return

    try:
        # --- Крок 1: Отримуємо структуру від Gemini ---
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        Створи структуру для 5-слайдової презентації в журнальному стилі на тему '{topic}'.
        Дотримуйся чіткого JSON формату. Жодного тексту поза JSON.
        'slide_text' має бути списком з 3-4 коротких пунктів (починаючи з '- ').
        'image_prompt' має бути деталізованим описом англійською мовою для AI-генератора фото.
        
        Приклад JSON:
        {{
          "main_title": "Заголовок Презентації про {topic}",
          "slides": [
            {{
              "slide_title": "Слайд 1: Вступ",
              "slide_text": "- Пункт 1...\n- Пункт 2...\n- Пункт 3...",
              "image_prompt": "high-quality cover art, professional, {topic}"
            }},
            {{
              "slide_title": "Слайд 2: Основна частина",
              "slide_text": "- Пункт 1...\n- Пункт 2...\n- Пункт 3...",
              "image_prompt": "detailed photorealistic image related to slide 2 topic"
            }},
            {{
              "slide_title": "Слайд 3: Деталі",
              "slide_text": "- Пункт 1...\n- Пункт 2...\n- Пункт 3...",
              "image_prompt": "symbolic or abstract image for slide 3 topic"
            }},
            {{
              "slide_title": "Слайд 4: Приклади",
              "slide_text": "- Пункт 1...\n- Пункт 2...\n- Пункт 3...",
              "image_prompt": "a graph or infographic related to slide 4 topic"
            }},
            {{
              "slide_title": "Слайд 5: Висновок",
              "slide_text": "- Пункт 1...\n- Пункт 2...",
              "image_prompt": "a hopeful or futuristic image for the conclusion"
            }}
          ]
        }}
        """
        
        response = model.generate_content(prompt)
        
        # --- Крок 2: Парсимо JSON ---
        try:
            # Gemini може повернути JSON у ` ```json ... ``` `
            raw_json = re.search(r"\{.*\}", response.text, re.DOTALL).group(0)
            data = json.loads(raw_json)
            main_title = data.get("main_title", topic)
            slides = data.get("slides", [])
            if not slides: raise ValueError("Gemini повернув порожні слайди")
        except Exception as e:
            raise ValueError(f"Не вдалося розпарсити JSON від Gemini. {e}")

        # --- Крок 3: Створюємо PDF та додаємо шрифти ---
        pdf = FPDF()
        
        try:
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
            font = 'DejaVu'
        except RuntimeError:
            print("ПОПЕРЕДЖЕННЯ: Шрифти DejaVu (DejaVuSans.ttf) не знайдено. Кирилиця не буде працювати.")
            font = 'Arial'
            
        # --- Крок 4: Титульна сторінка ---
        pdf.add_page()
        pdf.set_font(font, 'B', 24)
        pdf.multi_cell(0, 15, f"\n{main_title}\n", align='C')
        pdf.set_font(font, '', 14)
        pdf.multi_cell(0, 10, f"Тема: {topic}", align='C')
        
        bot.edit_message_text(f"<b>2/3: Генерую титульне фото... (Getimg.ai)</b>\n{progress_bar(30)}", cid, loading_msg["msg_id"])
        
        cover_prompt = slides[0].get("image_prompt", f"cover art for {topic}")
        cover_bytes = generate_image_for_slide(cover_prompt) 
        
        if cover_bytes:
            try:
                temp_img_path = f"temp_cover_{cid}.jpg"
                with open(temp_img_path, "wb") as f:
                    f.write(cover_bytes)
                
                pdf.image(temp_img_path, x=10, y=pdf.get_y() + 10, w=190, h=107) 
                os.remove(temp_img_path) 
            except Exception as e:
                print(f"Не вдалося вставити титульне фото (Getimg.ai): {e}")
        else:
             print("Фото для титулки не згенеровано (Getimg.ai error?).")

        # --- Крок 5: Слайди контенту ---
        progress_step = 60 // len(slides)
        
        for i, slide in enumerate(slides):
            pdf.add_page()
            pdf.set_font(font, 'B', 18)
            pdf.multi_cell(0, 10, f'\n{slide.get("slide_title", "")}\n', align='C')
            
            current_progress = 30 + (i+1) * progress_step
            bot.edit_message_text(f"<b>3/3: Генерую слайд {i+1}/{len(slides)}... (Getimg.ai)</b>\n{progress_bar(current_progress)}", cid, loading_msg["msg_id"])

            img_bytes = generate_image_for_slide(slide.get("image_prompt", f"abstract image for {topic}"))
            
            if img_bytes:
                try:
                    temp_img_path = f"temp_slide_{cid}_{i}.jpg"
                    with open(temp_img_path, "wb") as f:
                        f.write(img_bytes)
                    
                    pdf.image(temp_img_path, x=10, y=pdf.get_y() + 5, w=190, h=107) 
                    pdf.ln(107 + 5)
                    os.remove(temp_img_path) 
                except Exception as e:
                    print(f"Не вдалося завантажити/вставити фото слайду {i} (Getimg.ai): {e}")
            else:
                 print(f"Фото для слайду {i} не згенеровано (Getimg.ai error?).")
            
            pdf.ln(5)
            pdf.set_font(font, '', 12)
            pdf.multi_cell(0, 8, slide.get("slide_text", ""))

        # --- Крок 6: Відправка PDF ---
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        stop_progress(cid)
        bot.send_document(cid, buffer, caption=f"<b>{topic}</b>", filename=f"{topic[:50]}.pdf", reply_markup=main_menu())

    except Exception as e:
        stop_progress(cid)
        print(f"Критична помилка gen_pres: {e}")
        bot.send_message(cid, f"[Error] Помилка створення PDF: {str(e)[:1000]}", reply_markup=main_menu())


# -------------------------------------------------------------------
# ✅ ПИТАННЯ (ПЕРЕВЕДЕНО НА GEMINI)
# -------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "❓ Відповіді на питання")
def ask_q(m):
    bot.send_message(m.chat.id, "<b>ЗАДАЙ ПИТАННЯ:</b>\nПриклад: <code>Коли я стану мільйонером?</code>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, answer_q)

def answer_q(m):
    cid = m.chat.id
    q = m.text.strip()
    ensure_user_data(cid)
    user_data[cid]["questions"].append(q)
    
    start_progress(cid, "ДУМАЮ... (Gemini)")
    if not GEMINI_API_KEY:
        stop_progress(cid)
        bot.send_message(cid, "[Warning] Gemini API ключ не налаштований.", reply_markup=main_menu())
        return
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Відповідь: {q}. 3 абзаци, фото, відео YouTube, 2 джерела."
        
        response = model.generate_content(prompt)
        stop_progress(cid)
        bot.send_message(cid, response.text, disable_web_page_preview=False, reply_markup=main_menu())
    except Exception as e:
        stop_progress(cid)
        bot.send_message(cid, f"[Error] Помилка Gemini: {str(e)[:100]}", reply_markup=main_menu())

# ======== FLASK WEBHOOK ========
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return '', 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        print(f"ОТРИМАНО UPDATE: {json_string[:200]}")
        update = telebot.types.Update.de_json(json_string)
        if update:
            bot.process_new_updates([update])
        return "OK", 200
    return "", 400

# ======== АВТО-WEBHOOK ========
try:
    info = bot.get_webhook_info()
    if info.url != WEBHOOK_URL:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        print(f"Webhook встановлено: {WEBHOOK_URL}")
    else:
        print(f"Webhook активний: {info.url}")
except Exception as e:
    print(f"Помилка webhook: {e}")

print("Бот запущено! Слава ЗСУ!")
