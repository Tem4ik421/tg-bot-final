# Використовуємо чистий, стабільний образ Alpine
FROM alpine:latest

# Додаємо Edge-репозиторій для встановлення wkhtmltopdf
RUN echo "@edge http://nl.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories && \
    echo "@edge http://nl.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories

# Встановлюємо wkhtmltopdf, Python та всі необхідні залежності
RUN apk update && \
    apk add --no-cache python3 py3-pip wkhtmltopdf@edge \
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