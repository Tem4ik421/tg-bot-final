import google.generativeai as genai

# 💡 ВСТАВЬ свой реальный ключ прямо сюда:
genai.configure(api_key="AIzaSyDjQvlVSIAd9--TEjfHZuxrAOkZMJZ7_pE")

print("🔍 Проверяю доступные модели Gemini...\n")

try:
    models = genai.list_models()
    for m in models:
        print(f"➡️ {m.name} — методы: {m.supported_generation_methods}")
    print("\n✅ Проверка завершена. Скопируй список сюда, чтобы я помог выбрать рабочую модель.")
except Exception as e:
    print(f"❌ Ошибка при запросе моделей: {e}")

