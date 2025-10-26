# Використовуємо стабільний образ Python на базі Debian (Slim)
FROM python:3.11-slim

# --- ВСТАНОВЛЕННЯ СИСТЕМНИХ ЗАЛЕЖНОСТЕЙ ДЛЯ WEASYPRINT ---
# Ці пакети необхідні для рендерингу графіки та шрифтів (Cairo, Pango, HarfBuzz)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-dev \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    g++ \
    gcc \
    # Очищення кешу, щоб зменшити розмір образу
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- ВСТАНОВЛЕННЯ PYTHON-ЗАЛЕЖНОСТЕЙ ---
# Створюємо робочу директорію
WORKDIR /app
# Копіюємо requirements.txt та встановлюємо пакети
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо решту файлів проєкту (main.py, тощо)
COPY . .

# --- КОМАНДА ЗАПУСКУ БОТА ---
# Використовуємо прямий запуск main.py, оскільки він містить логіку Flask/Webhook
# (якщо ви використовуєте Gunicorn, використовуйте CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "main:app"])
CMD ["python3", "main.py"]