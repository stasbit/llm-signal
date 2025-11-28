#!/usr/bin/env python3
from __future__ import annotations

import json
import datetime
from pathlib import Path
from typing import Any, Dict, List

# === Параметры/пути ===
BASE = Path(__file__).resolve().parent.parent.parent
AF_DIR = BASE / "auto_feedback"
LESSONS_DIR = AF_DIR / "lessons"
ROLLING_PATH = LESSONS_DIR / "rolling.jsonl"
LESSONS_MD = LESSONS_DIR / "LESSONS_FOR_LLM.md"
AUTO_LESSONS = LESSONS_DIR / "Auto_Lessons.md"

# лимиты
ROLLING_MAX = 10000   # safety cap, чтобы файл бесконечно не рос
LESSONS_MAX = 200     # сколько строк включаем в Markdown

# создаём директории
AF_DIR.mkdir(exist_ok=True, parents=True)
LESSONS_DIR.mkdir(exist_ok=True, parents=True)

# допустимые значения
RESULT_OK = {"win", "loss", "breakeven", "skip"}
EXIT_OK   = {"tp1","tp2","sl","breakeven","no_entry","cancel","manual","timeout"}

def _month_dir(dt: datetime.datetime) -> Path:
    month = dt.strftime("%Y-%m")
    p = AF_DIR / month
    p.mkdir(parents=True, exist_ok=True)
    return p

def _safe_pair(pair: str) -> str:
    return (pair or "UNKNOWN").replace("/", "_").replace(" ", "")

def validate(d: Dict[str, Any]) -> Dict[str, Any]:
    """Минимальная валидация и нормализация полей v1."""
    # обязательные поля
    for k in ("pair","result"):
        if k not in d:
            raise ValueError(f"missing field: {k}")

    if d["result"] not in RESULT_OK:
        raise ValueError(f"result must be one of {sorted(RESULT_OK)}")

    if d.get("exit_reason"):
        if d["exit_reason"] not in EXIT_OK:
            raise ValueError(f"wrong exit_reason (allowed: {sorted(EXIT_OK)})")

    # нормализуем datetime в ISO, если отсутствует
    if not d.get("datetime"):
        d["datetime"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return d

def _cap_rolling_if_needed() -> None:
    """Поддерживаем размер rolling.jsonl в разумных границах."""
    try:
        text = ROLLING_PATH.read_text(encoding="utf-8")
    except Exception:
        return
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) <= ROLLING_MAX:
        return
    # оставляем последние ROLLING_MAX строк
    ROLLING_PATH.write_text("\n".join(lines[-ROLLING_MAX:]) + "\n", encoding="utf-8")

def rebuild_lessons_md() -> int:
    """
    Сборка авто-уроков:
    - читает auto_feedback/lessons/rolling.jsonl (feedback-сниппеты)
    - рендерит краткие строки
    - ДОБАВЛЯЕТ в конец AUTO-блок (Auto_Lessons.md), если он существует
    Возвращает число feedback-элементов (без AUTO-блока).
    """
    items: List[str] = []
    if ROLLING_PATH.exists():
        for ln in ROLLING_PATH.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue

            dt     = d.get("datetime") or d.get("ts") or ""
            pair   = d.get("pair", "")
            res    = d.get("result", "")
            issues = d.get("issues") or []
            fixes  = d.get("fixes")  or []
            if not isinstance(issues, list): issues = []
            if not isinstance(fixes, list):  fixes  = []
            issues_str = ", ".join(issues) if issues else "none"
            fixes_str  = ", ".join(fixes)  if fixes  else "none"

            note = ""
            pnl = d.get("pnl")
            if isinstance(pnl, dict):
                note = pnl.get("note") or ""
            if not note:
                note = d.get("comment", "") or "—"

            items.append(f"- {dt} • {pair} • result={res}; issues=[{issues_str}]; fixes=[{fixes_str}]; note: {note}")

    # ограничим хвостом, чтобы промпт не раздувался
    tail = items[-min(len(items), LESSONS_MAX):]
    header = "# [LESSONS]\n" \
             "Учитывай повторяющиеся ошибки и принятые фиксы при генерации сигнала. " \
             "Ниже последние случаи (свежие внизу):\n\n"
    text = header + "\n".join(tail) + "\n"

    # приклеиваем AUTO (если есть)
    if AUTO_LESSONS.exists():
        auto_txt = AUTO_LESSONS.read_text(encoding="utf-8").strip()
        if auto_txt:
            text += "\n" + auto_txt + "\n"

    LESSONS_MD.write_text(text, encoding="utf-8")
    return len(items)

def save_feedback(data: Dict[str, Any]) -> str:
    d = validate(dict(data))  # копия и валидация

    # вычисляем имя файла
    now = datetime.datetime.now(datetime.timezone.utc)
    monthdir = _month_dir(now)
    pair = _safe_pair(d.get("pair"))
    sid = (d.get("signal_id") or now.strftime("%Y%m%d_%H%M%S"))
    json_path = monthdir / f"feedback_{pair}_{sid}.json"

    # сохраняем сам сниппет (красиво)
    json_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    # добавляем в rolling.jsonl (одной строкой)
    with ROLLING_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # ограничим размер rolling на всякий
    _cap_rolling_if_needed()

    # пересоберём LESSONS_FOR_LLM.md
    n = rebuild_lessons_md()

    print(f"✅ Feedback saved: {json_path}")
    print(f"🔁 LESSONS rebuilt: {LESSONS_MD} ({n} items)")
    return str(json_path)

if __name__ == "__main__":
    import sys
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            data = json.loads(raw)
        else:
            if len(sys.argv) < 2:
                raise SystemExit("Usage: feedback_writer.py < file.json")
            with open(sys.argv[1], "r", encoding="utf-8") as fh:
                data = json.load(fh)
        save_feedback(data)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
