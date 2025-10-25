# Використовуємо образ Python на базі Debian (slim) - це набагато стабільніше для wkhtmltopdf
FROM python:3.11-slim

# --- ВСТАНОВЛЕННЯ WKHTMLTOPDF З APT ---
# Оновлюємо систему та встановлюємо wkhtmltopdf і необхідні залежності/шрифти
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# --- Встановлення Python-залежностей ---
WORKDIR /app

COPY requirements.txt .
# Встановлення залежностей Python
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]