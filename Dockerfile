# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем зависимости
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы бота
COPY . .

# Указываем команду для запуска бота
CMD ["python", "main.py"]
