# --- Обычные функции ---

import re

async def update_channels_and_restart_handler(new_channels, CHANNELS, register_handler):
    """Обновляет список каналов и перезапускает обработчик"""
    CHANNELS.clear()
    CHANNELS.extend(new_channels)
    await register_handler()



def is_russia_only_citizenship(text: str) -> bool:
    """
    Проверяет гражданство строго после слова 'Гражданство'.
    ОТСЕКАЕТ, если указано только Россия/РФ без упоминания РБ.
    ПРОХОДИТ, если есть РБ вместе с РФ.
    """
    # Расширенные шаблоны для отсечения РФ
    russia_only_patterns = [
        r"\bрф\b",
        r"\bроссия\b",
        r"только\s*рф",
        r"только\s*россия",
        r"только\s*гражданство\s*рф",
        r"паспорт\s*рф\s*обязателен",
        r"только\s*россияне",
        r"только\s*граждане\s*рф",
        r"налоговое\s*резидентство\s*рф\s*обязательно",
        r"из\s*рф",
        r"жители\s*рф",
        r"работа\s*из\s*любой\s*точки\s*рф",
        r"лок:\s*рф",
        r"оформление\s*в\s*рф"
    ]

    # Ищем строку после слова "Гражданство"
    match = re.search(r"Гражданство\s*[:\-]?\s*(.+)", text, flags=re.IGNORECASE)
    if match:
        citizenship = match.group(1).lower()
        # Если упоминается Беларусь — НЕ отсекать
        if "рб" in citizenship or "беларусь" in citizenship:
            return False
        # Проверяем все шаблоны РФ
        for pattern in russia_only_patterns:
            if re.search(pattern, citizenship):
                return True
    return False
