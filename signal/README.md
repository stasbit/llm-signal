# Signal Bot

Telegram бот для генерации торговых сигналов на основе анализа рынка с использованием LLM.

## Структура проекта

```
signal/
├── signal/              # Основной код приложения
│   ├── bot/            # Telegram бот
│   ├── core/           # Основная логика генерации сигналов
│   └── utils/          # Вспомогательные утилиты
├── scripts/            # Скрипты запуска
├── config/             # Конфигурационные файлы и промпты
├── tests/              # Тесты
├── docs/               # Документация
├── auto_feedback/      # Автоматические отзывы и уроки
└── local_backups/      # Локальные резервные копии
```

## Установка

1. Создайте виртуальное окружение:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env.tg` с настройками:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_TARGET_CHANNEL=your_channel_id
TELEGRAM_ALLOWED_USER_IDS=user_id1,user_id2
```

## Использование

Запуск бота:
```bash
python signal/bot/tg_bot.py
```

Генерация сигнала:
```bash
./scripts/signal --symbol BTC/USDT
```

Генерация сигналов для всех символов:
```bash
./scripts/signal full
```

## Конфигурация

- `config/params.json` - параметры модели и генерации
- `config/pool.json` - список торговых пар
- `config/prompt_*.txt` - промпты для LLM

