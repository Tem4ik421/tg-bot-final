# Використовуємо образ, де wkhtmltopdf вже встановлено
FROM customorbis/python-wkhtmltopdf:3.11-alpine-0.12.6

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо requirements.txt та встановлюємо Python-залежності
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копіюємо решту файлів проєкту в контейнер
COPY . .

# Команда для запуску бота
CMD ["python", "main.py"]
