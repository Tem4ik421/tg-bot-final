# Використовуємо чистий образ Python для Alpine
FROM python:3.11-alpine

# --- ВСТАНОВЛЕННЯ WKHTMLTOPDF (v0.12.6) ---
# Оновлюємо систему та встановлюємо інструменти для завантаження (wget)
# Також встановлюємо libstdc++, необхідний для запуску wkhtmltopdf
RUN apk update && apk add --no-cache wget libstdc++

# Завантажуємо нову версію wkhtmltopdf (v0.12.6 для Alpine 3.12)
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.alpine312_amd64.tar.xz && \
    tar xvf wkhtmltox_0.12.6-1.alpine312_amd64.tar.xz && \
    cp wkhtmltox/bin/wkhtmltopdf /usr/bin/wkhtmltopdf && \
    rm -rf wkhtmltox_0.12.6-1.alpine312_amd64.tar.xz wkhtmltox

# --- Встановлення Python-залежностей ---
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]