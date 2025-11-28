#!/usr/bin/env python3
"""
tg_bot.py - Telegram бот для генерации и отправки торговых сигналов

Основное назначение:
    Telegram бот, который принимает команды от пользователей и запускает
    генерацию торговых сигналов через скрипт signal. Результаты отправляются
    в указанный Telegram канал.

Архитектура:
    1. Принимает команды через Telegram (текстовые кнопки и команды)
    2. Запускает скрипт signal через subprocess
    3. Читает результаты (HTML, JSON, Markdown файлы)
    4. Отправляет в канал и пользователю

Основные функции:
    - /start - запуск бота, главное меню
    - /whoami - информация о пользователе
    - 📊 Сигнал - меню выбора актива для генерации сигнала
    - 📈 Анализ - полный анализ рынка (MULTI режим)
    - 🤖 Auto (FULL) - автоматический полный анализ
    - Выбор символа (BTC, ETH и т.д.) - генерация сигнала для актива

Зависимости:
    - python-telegram-bot
    - Доступ к скрипту signal в signal/scripts/
    - Файлы конфигурации: .env.tg, config/pool.json
"""

import os
import re
import subprocess
import html as htmllib
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================================

BASE = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE / ".env.tg")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_TARGET_CHANNEL")

# ============================================================================
# КОНФИГУРАЦИЯ И БЕЗОПАСНОСТЬ
# ============================================================================

def parse_allowed_ids() -> list[int]:
    """
    Парсит список разрешенных пользователей из переменных окружения.
    
    Поддерживает два формата:
    - TELEGRAM_ALLOWED_USER_IDS (новый, множественные ID через запятую/точку с запятой)
    - TELEGRAM_ALLOWED_USER_ID (старый, один ID)
    
    Returns:
        Список уникальных ID пользователей
    """
    ids = []
    raw_multi = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    raw_legacy = os.getenv("TELEGRAM_ALLOWED_USER_ID", "")
    for raw in (raw_multi, raw_legacy):
        for x in raw.replace(";", ",").split(","):
            x = x.strip()
            if x and x.lstrip("-").isdigit():
                ids.append(int(x))
    return list(dict.fromkeys(ids))

ALLOWED_UIDS = parse_allowed_ids()

# Загружаем список доступных символов из конфигурации
try:
    _pool = json.load(open(BASE / "config/pool.json", "r", encoding="utf-8"))["pool"]
    SYMBOLS = [s.split("/")[0] for s in _pool]
except Exception:
    # Fallback на дефолтный список, если не удалось загрузить конфигурацию
    SYMBOLS = ["BTC", "ETH", "SOL", "AVAX", "APT", "AAVE", "LINK", "TON", "ARB"]
SYMBOLS_SET = set(SYMBOLS)

# Персонализированные приветствия для пользователей
GREETINGS = {
    87017886: "Привет, Ирина! 👋",
}

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def make_header(title: str) -> str:
    """
    Создает заголовок сообщения с текущей датой и временем.
    
    Args:
        title: Текст заголовка
    
    Returns:
        Строка в формате "title • dd.mm.yyyy HH:MM"
    """
    return f"{title} • {datetime.now().strftime('%d.%m.%Y %H:%M')}"

def is_allowed(uid: int) -> bool:
    """
    Проверяет, разрешен ли доступ пользователю.
    
    Args:
        uid: Telegram user ID
    
    Returns:
        True если пользователь в списке разрешенных, иначе False
    """
    return (uid in ALLOWED_UIDS) if ALLOWED_UIDS else False

def latest(pattern: str) -> Path | None:
    """
    Находит самый новый файл по паттерну (по времени модификации).
    
    Args:
        pattern: Glob паттерн для поиска файлов (например, "logs/*.json")
    
    Returns:
        Path к самому новому файлу или None, если файлов не найдено
    """
    files = list(BASE.glob(pattern))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None

def html_file_to_tg_text(p: Path, max_len: int = 4000) -> list[str]:
    """
    Конвертирует HTML файл в текст для Telegram, разбивая на части.
    
    Удаляет HTML теги и экранирует HTML сущности. Разбивает длинный текст
    на части по max_len символов (лимит Telegram ~4096 символов).
    
    Args:
        p: Путь к HTML файлу
        max_len: Максимальная длина одной части (по умолчанию 4000)
    
    Returns:
        Список строк, каждая не длиннее max_len
    """
    s = p.read_text(encoding="utf-8")
    s = re.sub(r"<[^>]+>", "", s)  # Удаляем HTML теги
    s = htmllib.unescape(s).strip()  # Декодируем HTML сущности
    chunks = []
    while s:
        chunks.append(s[:max_len])
        s = s[max_len:]
    return chunks

def md_file_to_chunks(p: Path, max_len: int = 4000) -> list[str]:
    """
    Разбивает Markdown файл на части для отправки в Telegram.
    
    Args:
        p: Путь к Markdown файлу
        max_len: Максимальная длина одной части
    
    Returns:
        Список строк, каждая не длиннее max_len
    """
    s = p.read_text(encoding="utf-8").strip()
    chunks = []
    while s:
        chunks.append(s[:max_len])
        s = s[max_len:]
    return chunks

def run_signal_command(command: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """
    Запускает скрипт signal с указанной командой.
    
    Использует BASE для определения пути к скрипту, что делает функцию
    независимой от расположения проекта на сервере.
    
    Args:
        command: Команда для signal (например, "full" или "--symbol 'BTC/USDT'")
        timeout: Таймаут выполнения в секундах (по умолчанию 600 для SINGLE, 900 для MULTI)
    
    Returns:
        Результат выполнения subprocess.run() с stdout и stderr
    
    Raises:
        subprocess.TimeoutExpired: Если выполнение превысило timeout
    """
    signal_script = BASE / "scripts" / "signal"
    cmd = f"cd {BASE} && {signal_script} {command}"
    return subprocess.run(
        ["bash", "-lc", cmd],
        capture_output=True,
        text=True,
        timeout=timeout
    )

# ============================================================================
# КЛАВИАТУРЫ (МЕНЮ)
# ============================================================================

def main_menu_kb() -> ReplyKeyboardMarkup:
    """
    Создает главное меню бота с основными опциями.
    
    Returns:
        ReplyKeyboardMarkup с кнопками "📊 Сигнал" и "📈 Анализ"
    """
    kb = [[KeyboardButton("📊 Сигнал")], [KeyboardButton("📈 Анализ")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def signal_menu_kb() -> ReplyKeyboardMarkup:
    """
    Создает меню выбора актива для генерации сигнала.
    
    Загружает список активов из config/pool.json и создает кнопки:
    - "🤖 Auto (FULL)" - автоматический полный анализ
    - Кнопки с символами (по 3 в ряд)
    - "⬅️ Назад" - возврат в главное меню
    
    Returns:
        ReplyKeyboardMarkup с кнопками выбора активов
    """
    try:
        pool = json.load(open(BASE / "config/pool.json", "r", encoding="utf-8"))["pool"]
    except Exception:
        # Fallback на дефолтный список
        pool = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "APT/USDT", 
                "AAVE/USDT", "LINK/USDT", "TON/USDT", "ARB/USDT"]
    short = [s.split("/")[0] for s in pool]
    rows = [[KeyboardButton("🤖 Auto (FULL)")]]
    # Группируем символы по 3 в ряд
    for i in range(0, len(short), 3):
        rows.append([KeyboardButton(x) for x in short[i:i+3]])
    rows.append([KeyboardButton("⬅️ Назад")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ============================================================================
# ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ
# ============================================================================

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /whoami - показывает информацию о пользователе и настройках бота.
    
    Полезно для отладки и проверки доступа.
    """
    uid = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(
        f"whoami\n"
        f"- your id: {uid}\n"
        f"- allowed: {ALLOWED_UIDS}\n"
        f"- channel: {CHANNEL}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /start - запуск бота и показ главного меню.
    
    Проверяет доступ пользователя и показывает персонализированное приветствие.
    """
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return
    first = (update.effective_user.first_name or "").strip()
    hello = GREETINGS.get(uid) or (f"Привет, {first}!" if first else "Привет!")
    await update.message.reply_text(hello)
    await update.message.reply_text("📋 Главное меню", reply_markup=main_menu_kb())

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик кнопки "⬅️ Назад" - возврат в главное меню.
    """
    await update.message.reply_text("📋 Главное меню", reply_markup=main_menu_kb())

async def handle_signal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик кнопки "📊 Сигнал" - показывает меню выбора актива.
    """
    await update.message.reply_text("Выбери актив или режим:", reply_markup=signal_menu_kb())

async def handle_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик кнопки "🤖 Auto (FULL)" - запускает полный анализ рынка.
    
    Процесс:
    1. Запускает signal full (MULTI режим)
    2. Читает результаты: analysis_*.md и signal_*.html
    3. Отправляет в канал анализ и сигнал
    """
    header = make_header("📝 LLM Full анализ")
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Нет доступа.")
        return
    
    msg = await update.message.reply_text("Запускаю FULL анализ… это займёт немного времени.")
    
    # Запускаем MULTI режим (полный анализ пула)
    proc = run_signal_command("full", timeout=900)
    
    # Ищем сгенерированные файлы
    analysis = latest("analysis_*.md")
    sig_html = latest("signal_*.html")
    
    # Отправляем анализ в канал (до раздела "2️⃣ Сетап")
    if analysis:
        text = Path(analysis).read_text(encoding="utf-8").split("2️⃣ Сетап")[0].strip()
        await context.bot.send_message(chat_id=CHANNEL, text=header + "\n\n" + text)
    
    # Отправляем сигнал в канал
    if sig_html:
        parts = html_file_to_tg_text(Path(sig_html))
        await context.bot.send_message(chat_id=CHANNEL, text="📣 Сигнал\n\n" + parts[0])

async def handle_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик кнопки "📈 Анализ" - запускает анализ рынка без сигнала.
    
    Процесс:
    1. Запускает signal full (MULTI режим)
    2. Читает analysis_*.md
    3. Отправляет в канал только аналитическую часть (без сетапа)
    4. Показывает пользователю последние строки лога
    """
    header = make_header("📝 LLM Анализ")
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return
    
    msg = await update.message.reply_text("Запускаю анализ рынка… это займёт немного времени.")
    
    # Запускаем MULTI режим
    proc = run_signal_command("full", timeout=900)
    
    # Ищем файл анализа
    analysis = latest("analysis_*.md")
    if not analysis:
        await msg.edit_text("Не удалось сформировать анализ.")
        return
    
    # Отправляем только аналитическую часть (до раздела "2️⃣ Сетап")
    text = Path(analysis).read_text(encoding="utf-8").split("2️⃣ Сетап")[0].strip()
    await context.bot.send_message(chat_id=CHANNEL, text=header + "\n" + text)
    
    # Показываем пользователю последние строки лога
    safe_tail = htmllib.escape("\n".join(proc.stdout.splitlines()[-20:]) or "(лог пуст)")
    await msg.edit_text(f"Готово\n<pre>{safe_tail}</pre>", parse_mode=ParseMode.HTML)

async def handle_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик выбора символа (BTC, ETH и т.д.) - генерирует сигнал для конкретного актива.
    
    Процесс:
    1. Проверяет доступ пользователя
    2. Валидирует выбранный символ
    3. Запускает signal --symbol SYMBOL/USDT (SINGLE режим)
    4. Читает результаты: signal_*.html и logs/last.raw.json
    5. Отправляет в канал:
       - Полный HTML сигнал (разбитый на части)
       - Мини-блок с ключевыми параметрами (диапазон входа, режим, уверенность)
    6. Показывает пользователю последние строки лога
    
    Args:
        update: Telegram update объект
        context: Контекст бота
    """
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Нет доступа.")
        return

    # Шаг 1: Валидация символа
    sym_text = (update.message.text or "").strip().upper()
    if sym_text not in SYMBOLS_SET:
        await update.message.reply_text("Не распознал символ. Выбери из меню.")
        return
    symbol = f"{sym_text}/USDT"

    # Шаг 2: Уведомление пользователя
    msg = await update.message.reply_text(f"Готовлю сигнал по {symbol}…")

    # Шаг 3: Запускаем SINGLE режим (сигнал для одного актива)
    proc = run_signal_command(f"--symbol '{symbol}'", timeout=600)

    # Шаг 4: Отправляем полный сигнал в канал
    sig_html = latest("signal_*.html")
    if sig_html:
        parts = html_file_to_tg_text(Path(sig_html))
        parts[0] = "📣 Сигнал\n\n" + parts[0]
        await context.bot.send_message(chat_id=CHANNEL, text=parts[0])
        # Отправляем остальные части, если текст длинный
        for chunk in parts[1:]:
            await context.bot.send_message(chat_id=CHANNEL, text=chunk)

    # Шаг 5: Отправляем мини-блок с ключевыми параметрами
    # Формат: символ | диапазон входа | режим | уверенность | подтверждение
    try:
        last_raw = latest("logs/last.raw.json")
        if last_raw:
            data = json.loads(Path(last_raw).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                sym = data.get("symbol") or symbol
                er = (data.get("entry_range") or {})
                er_min = er.get("min") if er.get("min") is not None else "—"
                er_max = er.get("max") if er.get("max") is not None else "—"
                entry_mode = (data.get("entry_mode") or "limit")
                confidence = (data.get("confidence") or "Medium")
                confirm = data.get("confirmation_rules") or data.get("break_even_rule") or ""
                confirm = (confirm or "—").strip()
                mini = (
                    "📊 " + str(sym) + "\n"
                    "🎯 " + str(er_min) + "–" + str(er_max) + "  |  " + entry_mode + "  |  " + confidence + "\n"
                    "☑ " + confirm
                )
                await context.bot.send_message(chat_id=CHANNEL, text=mini)
    except Exception:
        # Игнорируем ошибки при парсинге мини-блока (не критично)
        pass

    # Шаг 6: Показываем пользователю последние строки лога
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-20:])
    await msg.edit_text(
        "Готово\n<pre>" + htmllib.escape(tail or "(лог пуст)") + "</pre>",
        parse_mode=ParseMode.HTML
    )

# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ И ЗАПУСК
# ============================================================================

def register_text_handlers(app: Application) -> None:
    """
    Регистрирует обработчики текстовых сообщений (кнопки меню и символы).
    
    Обрабатывает:
    - Кнопки меню: "📊 Сигнал", "📈 Анализ", "🤖 Auto (FULL)", "⬅️ Назад"
    - Символы активов: BTC, ETH, SOL и т.д. (из SYMBOLS_SET)
    
    Args:
        app: Экземпляр Application бота
    """
    # Обработчики кнопок меню
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📊 Сигнал$"), handle_signal_menu))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📈 Анализ$"), handle_analysis))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🤖 Auto \\(FULL\\)$"), handle_full))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^⬅️ Назад$"), handle_back))
    
    # Обработчик символов активов (динамический regex из списка символов)
    sym_regex = "^(" + "|".join(sorted(SYMBOLS_SET)) + ")$"
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(sym_regex), handle_symbol))

def main() -> None:
    """
    Главная функция запуска бота.
    
    Процесс:
    1. Проверяет наличие обязательных переменных окружения
    2. Создает экземпляр Application
    3. Регистрирует обработчики команд и сообщений
    4. Запускает бота в режиме polling
    """
    # Проверка обязательных настроек
    if not BOT_TOKEN or not CHANNEL:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_TARGET_CHANNEL in .env.tg")
    
    # Создание и настройка приложения
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("start", start))
    
    # Регистрация обработчиков текстовых сообщений
    register_text_handlers(app)
    
    # Запуск бота в режиме polling (ожидание обновлений)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
