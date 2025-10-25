# Використовуємо образ Python на базі Debian (slim)
FROM python:3.11-slim

# --- ВСТАНОВЛЕННЯ СИСТЕМНИХ ЗАЛЕЖНОСТЕЙ ДЛЯ WEASYPRINT ---
# Виправлено назви та додано всі необхідні dev-пакети.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-dev \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    g++ \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# --- Встановлення Python-залежностей ---
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуску бота
CMD ["python3", "main.py"]