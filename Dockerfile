# Використовуємо чистий образ Python для Alpine
FROM python:3.11-alpine

# --- ВСТАНОВЛЕННЯ WKHTMLTOPDF З БІНАРНОГО ФАЙЛА ---
# Оновлюємо систему та встановлюємо інструменти для завантаження (wget)
RUN apk update && apk add --no-cache wget

# Завантажуємо та встановлюємо wkhtmltopdf вручну
# Це надійне посилання на останній робочий бінарник
RUN wget https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.6/wkhtmltopdf-0.12.6.2.linux-static-amd64.tar.xz && \
    tar xvf wkhtmltopdf-0.12.6.2.linux-static-amd64.tar.xz && \
    cp wkhtmltox/bin/wkhtmltopdf /usr/bin/wkhtmltopdf && \
    rm -rf wkhtmltopdf-0.12.6.2.linux-static-amd64.tar.xz wkhtmltox

# --- Встановлення Python-залежностей ---
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]