# Використовуємо образ з встановленим wkhtmltopdf
FROM madduci/python-wkhtmltopdf:3.11-alpine-0.12.6

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо requirements.txt та встановлюємо Python-залежності
COPY requirements.txt .
# Видаляємо --no-cache-dir, щоб спростити виконання
RUN pip install -r requirements.txt

# Копіюємо решту файлів проєкту в контейнер
COPY . .

# ФІНАЛЬНЕ ВИПРАВЛЕННЯ: Використовуємо "python" замість "python3" для Alpine
CMD ["python", "main.py"]
