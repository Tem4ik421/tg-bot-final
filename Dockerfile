# Використовуємо образ Python на базі Debian (slim)
FROM python:3.11-slim

# --- ВСТАНОВЛЕННЯ WKHTMLTOPDF З .DEB-ПАКЕТА (Найнадійніший метод) ---
# Оновлюємо та встановлюємо необхідні залежності для wkhtmltopdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    libxrender1 \
    libfontconfig1 \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# Завантажуємо офіційний пакет wkhtmltopdf (v0.12.6 для Debian 11/Bullseye, це сумісно з Python 3.11-slim)
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bullseye_amd64.deb && \
    dpkg -i wkhtmltox_0.12.6-1.bullseye_amd64.deb && \
    rm wkhtmltox_0.12.6-1.bullseye_amd64.deb

# --- Встановлення Python-залежностей ---
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]