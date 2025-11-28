#!/usr/bin/env python3
import os, time, subprocess, re, html as htmllib, json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ===== базовая инициализация =====
BASE = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE / ".env.tg")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_TARGET_CHANNEL")

def parse_allowed_ids() -> list[int]:
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


# ===== список тикеров для single =====
try:
    _pool = json.load(open(BASE/"config/pool.json","r",encoding="utf-8"))["pool"]
    SYMBOLS = [s.split("/")[0] for s in _pool]
except Exception:
    SYMBOLS = ["BTC","ETH","SOL","AVAX","APT","AAVE","LINK","TON","ARB"]
SYMBOLS_SET = set(SYMBOLS)

GREETINGS = {
    87017886: "Привет, Ирина! 👋",
}

def make_header(title: str) -> str:
    """Единый формат заголовков, чтобы не было ошибок кавычек."""
    return f"{title} • {datetime.now().strftime('%d.%m.%Y %H:%M')}"

def is_allowed(uid: int) -> bool:
    return (uid in ALLOWED_UIDS) if ALLOWED_UIDS else False

def latest(pattern: str):
    files = list(BASE.glob(pattern))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None

def html_file_to_tg_text(p: Path, max_len=4000):
    s = p.read_text(encoding="utf-8")
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s).strip()
    chunks = []
    while s:
        chunks.append(s[:max_len])
        s = s[max_len:]
    return chunks

def md_file_to_chunks(p: Path, max_len=4000):
    s = p.read_text(encoding="utf-8").strip()
    chunks = []
    while s:
        chunks.append(s[:max_len])
        s = s[max_len:]
    return chunks

# ===== меню =====
def main_menu_kb():
    kb = [[KeyboardButton("📊 Сигнал")], [KeyboardButton("📈 Анализ")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def signal_menu_kb():
    try:
        pool = json.load(open(BASE / "config/pool.json", "r", encoding="utf-8"))["pool"]
    except Exception:
        pool = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "APT/USDT", "AAVE/USDT", "LINK/USDT", "TON/USDT", "ARB/USDT"]
    short = [s.split("/")[0] for s in pool]
    rows = [[KeyboardButton("🤖 Auto (FULL)")]]
    for i in range(0, len(short), 3):
        rows.append([KeyboardButton(x) for x in short[i:i+3]])
    rows.append([KeyboardButton("⬅️ Назад")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ===== handlers =====
async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(f"whoami\n- your id: {uid}\n- allowed: {ALLOWED_UIDS}\n- channel: {CHANNEL}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return
    first = (update.effective_user.first_name or "").strip()
    hello = GREETINGS.get(uid) or (f"Привет, {first}!" if first else "Привет!")
    await update.message.reply_text(hello)
    await update.message.reply_text("📋 Главное меню", reply_markup=main_menu_kb())

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Главное меню", reply_markup=main_menu_kb())

async def handle_signal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери актив или режим:", reply_markup=signal_menu_kb())

async def handle_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    header = make_header("📝 LLM Full анализ")
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Нет доступа.")
        return
    msg = await update.message.reply_text("Запускаю FULL анализ… это займёт немного времени.")
    proc = subprocess.run(["bash", "-lc", "cd ~/llm-signal && ./signal full"], capture_output=True, text=True, timeout=900)
    analysis = latest("analysis_*.md")
    sig_html = latest("signal_*.html")
    if analysis:
        text = Path(analysis).read_text(encoding="utf-8").split("2️⃣ Сетап")[0].strip()
        await context.bot.send_message(chat_id=CHANNEL, text=header + "\n\n" + text)
    if sig_html:
        parts = html_file_to_tg_text(Path(sig_html))
        await context.bot.send_message(chat_id=CHANNEL, text="📣 Сигнал\n\n" + parts[0])

async def handle_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    header = make_header("📝 LLM Анализ")
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return
    msg = await update.message.reply_text("Запускаю анализ рынка… это займёт немного времени.")
    proc = subprocess.run(["bash", "-lc", "cd ~/llm-signal && ./signal full"], capture_output=True, text=True, timeout=900)
    analysis = latest("analysis_*.md")
    if not analysis:
        await msg.edit_text("Не удалось сформировать анализ.")
        return
    text = Path(analysis).read_text(encoding="utf-8").split("2️⃣ Сетап")[0].strip()
    await context.bot.send_message(chat_id=CHANNEL, text=header + "\n" + text)
    safe_tail = htmllib.escape("\n".join(proc.stdout.splitlines()[-20:]) or "(лог пуст)")
    await msg.edit_text(f"Готово\n<pre>{safe_tail}</pre>", parse_mode=ParseMode.HTML)

# ===== main =====

async def handle_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    if not is_allowed(uid):
        await update.message.reply_text("Нет доступа.")
        return

    sym_text = (update.message.text or "").strip().upper()
    if sym_text not in SYMBOLS_SET:
        await update.message.reply_text("Не распознал символ. Выбери из меню.")
        return
    symbol = f"{sym_text}/USDT"

    msg = await update.message.reply_text(f"Готовлю сигнал по {symbol}…")

    import subprocess, json, html as _html
    proc = subprocess.run(
        ["bash","-lc", f"cd ~/llm-signal && ./signal --symbol '{symbol}'"],
        capture_output=True, text=True, timeout=600
    )

    # Отправляем полный сигнал в канал
    sig_html = latest("signal_*.html")
    if sig_html:
        parts = html_file_to_tg_text(sig_html)
        parts[0] = "📣 Сигнал\n\n" + parts[0]
        await context.bot.send_message(chat_id=CHANNEL, text=parts[0])
        for chunk in parts[1:]:
            await context.bot.send_message(chat_id=CHANNEL, text=chunk)

    # Мини-блок с диапазоном входа / режимом / уверенностью / подтверждением
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
        pass

    # Хвост лога пользователю
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-20:])
    await msg.edit_text("Готово\n<pre>" + _html.escape(tail or "(лог пуст)") + "</pre>", parse_mode=ParseMode.HTML)


def register_text_handlers(app: Application):
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📊 Сигнал$"), handle_signal_menu))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📈 Анализ$"), handle_analysis))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🤖 Auto \\(FULL\\)$"), handle_full))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^⬅️ Назад$"), handle_back))
    sym_regex = "^(" + "|".join(sorted(SYMBOLS_SET)) + ")$"
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(sym_regex), handle_symbol))

def main():
    if not BOT_TOKEN or not CHANNEL:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_TARGET_CHANNEL in .env.tg")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("start", start))
    register_text_handlers(app)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()


