# Використовуємо образ Python на базі Debian (slim)
FROM python:3.11-slim

# --- ВСТАНОВЛЕННЯ WKHTMLTOPDF З GCS (Найнадійніший метод) ---
# Оновлюємо систему та встановлюємо необхідні залежності та wget
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    libxrender1 \
    libfontconfig1 \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# Завантажуємо .deb-пакет v0.12.6 з Google Cloud Storage (GCS)
# Це посилання, як правило, не змінюється і повинно спрацювати.
RUN wget https://storage.googleapis.com/wkhtmltopdf/0.12.6/wkhtmltox_0.12.6-1.bullseye_amd64.deb && \
    dpkg -i wkhtmltox_0.12.6-1.bullseye_amd64.deb && \
    rm wkhtmltox_0.12.6-1.bullseye_amd64.deb

# --- Встановлення Python-залежностей ---
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]