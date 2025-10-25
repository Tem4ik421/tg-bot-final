# Використовуємо чистий, стабільний образ Python
FROM python:3.11-slim

# Встановлюємо wkhtmltopdf та всі необхідні системні залежності
# Це найнадійніша команда для встановлення wkhtmltopdf на Debian/Ubuntu
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    libxrender1 \
    libfontconfig1 \
    libxtst6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо requirements.txt та встановлюємо Python-залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо решту файлів проєкту в контейнер
COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]