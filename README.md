# LLM Signal

Репозиторий содержит два сервиса для генерации торговых сигналов с использованием LLM:

- **signal** - Telegram бот для генерации и отправки торговых сигналов
- **ai-agent** - FastAPI сервис для обработки сигналов через LangGraph

## Структура проекта

```
.
├── signal/          # Telegram бот для генерации сигналов
├── ai-agent/        # FastAPI сервис с LangGraph агентом
├── tools/           # Вспомогательные инструменты
└── status           # Скрипт для получения текущих цен
```

---

## Деплой сервисов

### Предварительные требования

- Python 3.10+
- Git
- Доступ к серверу (Linux)
- OpenAI API ключ
- Telegram Bot Token (для signal)

---

## 1. Деплой Signal Bot

### 1.1. Клонирование и установка

```bash
# Клонируем репозиторий
git clone https://github.com/stasbit/llm-signal.git
cd llm-signal/signal

# Создаем виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 1.2. Конфигурация

Создайте файл `.env` в директории `signal/`:

```bash
# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4.1-mini
```

Создайте файл `.env.tg` в директории `signal/`:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_TARGET_CHANNEL=@your_channel_username
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

### 1.3. Настройка путей

Убедитесь, что скрипт `signal` в `signal/scripts/signal` использует правильные пути. Если проект находится не в `~/llm-signal`, обновите пути в:
- `signal/signal/bot/tg_bot.py` (строка 117, 134, 162)
- `signal/signal/core/get_signal_json.py` (строка 138)

### 1.4. Деплой через systemd

Создайте файл `/etc/systemd/system/llm-signal-bot.service`:

```ini
[Unit]
Description=LLM Signal Telegram Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/llm-signal/signal
Environment="PATH=/path/to/llm-signal/signal/.venv/bin"
ExecStart=/path/to/llm-signal/signal/.venv/bin/python3 /path/to/llm-signal/signal/signal/bot/tg_bot.py
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

Активируйте и запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable llm-signal-bot
sudo systemctl start llm-signal-bot
sudo systemctl status llm-signal-bot
```

### 1.5. Ручной запуск

```bash
cd signal
source .venv/bin/activate
python signal/bot/tg_bot.py
```

### 1.6. Логи

```bash
# Просмотр логов systemd
sudo journalctl -u llm-signal-bot -f

# Логи генерации сигналов
tail -f signal/logs/signal_*.log
```

---

## 2. Деплой AI-Agent

### 2.1. Клонирование и установка

```bash
# Если еще не клонировали репозиторий
git clone https://github.com/stasbit/llm-signal.git
cd llm-signal/ai-agent

# Создаем виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 2.2. Конфигурация

Создайте файл `.env` в директории `ai-agent/`:

```bash
# Настройки приложения
APP_NAME=AI Trading Agent

# OpenAI API (если используется)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Другие настройки (при необходимости)
# DATABASE_URL=...
# REDIS_URL=...
```

### 2.3. Деплой через systemd

Создайте файл `/etc/systemd/system/llm-ai-agent.service`:

```ini
[Unit]
Description=LLM AI Agent FastAPI Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/llm-signal/ai-agent
Environment="PATH=/path/to/llm-signal/ai-agent/.venv/bin"
ExecStart=/path/to/llm-signal/ai-agent/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

Активируйте и запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable llm-ai-agent
sudo systemctl start llm-ai-agent
sudo systemctl status llm-ai-agent
```

### 2.4. Деплой с Gunicorn (рекомендуется для production)

Установите Gunicorn:

```bash
pip install gunicorn
```

Создайте файл `/etc/systemd/system/llm-ai-agent.service`:

```ini
[Unit]
Description=LLM AI Agent FastAPI Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/llm-signal/ai-agent
Environment="PATH=/path/to/llm-signal/ai-agent/.venv/bin"
ExecStart=/path/to/llm-signal/ai-agent/.venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

### 2.5. Ручной запуск

```bash
cd ai-agent
source .venv/bin/activate

# Простой запуск
uvicorn app.main:app --host 0.0.0.0 --port 8000

# С перезагрузкой при изменении кода (для разработки)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2.6. Проверка работы

```bash
# Health check
curl http://localhost:8000/health

# Документация API
# Откройте в браузере: http://localhost:8000/docs
```

### 2.7. Логи

```bash
# Просмотр логов systemd
sudo journalctl -u llm-ai-agent -f

# Логи агента
tail -f ai-agent/logs/journal.jsonl
```

---

## 3. Настройка Nginx (опционально)

Если нужно проксировать AI-Agent через Nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 4. Обновление сервисов

### Обновление Signal Bot

```bash
cd /path/to/llm-signal
git pull origin main
cd signal
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart llm-signal-bot
```

### Обновление AI-Agent

```bash
cd /path/to/llm-signal
git pull origin main
cd ai-agent
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart llm-ai-agent
```

---

## 5. Мониторинг и отладка

### Проверка статуса сервисов

```bash
# Signal Bot
sudo systemctl status llm-signal-bot

# AI-Agent
sudo systemctl status llm-ai-agent
```

### Просмотр логов в реальном времени

```bash
# Signal Bot
sudo journalctl -u llm-signal-bot -f

# AI-Agent
sudo journalctl -u llm-ai-agent -f
```

### Проверка портов

```bash
# Проверка, что AI-Agent слушает на порту 8000
netstat -tlnp | grep 8000
# или
ss -tlnp | grep 8000
```

---

## 6. Troubleshooting

### Signal Bot не запускается

1. Проверьте наличие файлов `.env` и `.env.tg`
2. Убедитесь, что токены корректны
3. Проверьте права доступа к файлам
4. Проверьте логи: `sudo journalctl -u llm-signal-bot -n 50`

### AI-Agent не отвечает

1. Проверьте, что сервис запущен: `sudo systemctl status llm-ai-agent`
2. Проверьте порт: `curl http://localhost:8000/health`
3. Проверьте логи: `sudo journalctl -u llm-ai-agent -n 50`
4. Убедитесь, что порт 8000 не занят другим процессом

### Проблемы с зависимостями

```bash
# Пересоздайте виртуальное окружение
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 7. Безопасность

- Никогда не коммитьте файлы `.env` и `.env.tg` в репозиторий
- Используйте сильные пароли и токены
- Ограничьте доступ к серверу через firewall
- Регулярно обновляйте зависимости
- Используйте HTTPS для production (через Nginx + Let's Encrypt)

---

## Контакты и поддержка

При возникновении проблем проверьте:
- Логи сервисов
- Конфигурационные файлы
- Статус systemd сервисов
- Доступность внешних API (OpenAI, Telegram)

