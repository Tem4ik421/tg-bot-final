# Використовуємо образ, який включає wkhtmltopdf
FROM darylteo/wkhtmltopdf-alpine:latest

# Встановлюємо робочу директорію
WORKDIR /app

# Встановлюємо Python та pip (цього не було в попередньому образі!)
RUN apk add --no-cache python3 py3-pip

# Копіюємо requirements.txt та встановлюємо Python-залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо решту файлів проєкту в контейнер
COPY . .

# Команда для запуску бота
