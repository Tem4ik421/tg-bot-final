# Використовуємо чистий, стабільний образ Alpine
FROM alpine:latest

# Встановлюємо Python, wkhtmltopdf та всі необхідні залежності
# Цей рядок гарантує, що всі інструменти встановлені коректно
RUN apk update && \
    apk add --no-cache python3 py3-pip wkhtmltopdf \
    && rm -rf /var/cache/apk/*

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо requirements.txt та встановлюємо Python-залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо решту файлів проєкту в контейнер
COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]