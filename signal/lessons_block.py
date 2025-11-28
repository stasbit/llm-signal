#!/usr/bin/env python3
"""
Модуль для загрузки уроков из auto_feedback/lessons/
"""
import json
from pathlib import Path
from typing import Tuple, List

BASE = Path(__file__).resolve().parent
LESSONS_DIR = BASE / "auto_feedback" / "lessons"
LESSONS_FILE = LESSONS_DIR / "LESSONS_FOR_LLM.md"
AUTO_LESSONS_FILE = LESSONS_DIR / "Auto_Lessons.md"


def load_lessons(limit: int = 0) -> Tuple[str, List[dict], int]:
    """
    Загружает уроки из файлов.
    
    Args:
        limit: Максимальное количество уроков (0 = без ограничений)
    
    Returns:
        Tuple[str, List[dict], int]: (текст уроков, список JSON объектов, количество)
    """
    lessons_text = ""
    lessons_list = []
    
    # Загружаем основной файл LESSONS_FOR_LLM.md
    if LESSONS_FILE.exists():
        lessons_text = LESSONS_FILE.read_text(encoding="utf-8").strip()
    
    # Загружаем Auto_Lessons.md если есть
    if AUTO_LESSONS_FILE.exists():
        auto_text = AUTO_LESSONS_FILE.read_text(encoding="utf-8").strip()
        if auto_text:
            if lessons_text:
                lessons_text += "\n\n" + auto_text
            else:
                lessons_text = auto_text
    
    # Парсим JSON файлы из папки feedback
    feedback_dir = BASE / "auto_feedback"
    if feedback_dir.exists():
        for year_month_dir in sorted(feedback_dir.glob("*/"), reverse=True):
            if not year_month_dir.is_dir():
                continue
            for json_file in sorted(year_month_dir.glob("feedback_*.json"), reverse=True):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        lessons_list.append(data)
                        if limit > 0 and len(lessons_list) >= limit:
                            break
                except Exception:
                    continue
            if limit > 0 and len(lessons_list) >= limit:
                break
    
    return lessons_text, lessons_list, len(lessons_list)


if __name__ == "__main__":
    text, items, count = load_lessons()
    print(f"Loaded {count} lessons")
    if text:
        print(f"Text length: {len(text)} chars")

