# Використовуємо образ Python на базі Debian (slim)
FROM python:3.11-slim

# --- ВСТАНОВЛЕННЯ СИСТЕМНИХ ЗАЛЕЖНОСТЕЙ ДЛЯ WEASYPRINT ---
# WeasyPrint вимагає libpango, libffi та ін.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangs-ft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# --- Встановлення Python-залежностей ---
WORKDIR /app

COPY requirements.txt .
# WeasyPrint (або інші потрібні бібліотеки) будуть тут
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]