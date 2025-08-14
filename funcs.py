import inspect
from collections import namedtuple
if not hasattr(inspect, "getargspec"):
    ArgSpec = namedtuple('ArgSpec', ['args', 'varargs', 'keywords', 'defaults'])
    def getargspec(func):
        spec = inspect.getfullargspec(func)
        return ArgSpec(
            args=spec.args,
            varargs=spec.varargs,
            keywords=spec.varkw,
            defaults=spec.defaults,
        )
    inspect.getargspec = getargspec

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



import pymorphy2

def oplata_filter(text: str) -> bool:
    morph = pymorphy2.MorphAnalyzer()
    filters_raw = [
        "акты поквартально", "квартальное актирование",
        "поквартальная оплата", "актирование",
        "поквартально", "квартальная оплата", "поквартальная"
    ]

    # Приводим текст к нижнему регистру
    text_lower = text.lower()
    
    # Сначала проверяем полные фразы
    for phrase in filters_raw:
        if phrase.lower() in text_lower:
            return True
    
    # Если фразы не найдены, проверяем отдельные слова
    text_words = text_lower.split()
    
    for word in text_words:
        # Нормализуем слово для сравнения
        parsed_word = morph.parse(word)[0]
        normal_word = parsed_word.normal_form
        
        # Проверяем, есть ли это слово в списке фильтров
        for filter_phrase in filters_raw:
            filter_words = filter_phrase.lower().split()
            for filter_word in filter_words:
                # Ищем только квартальные термины, игнорируем просто "оплата"
                if normal_word == filter_word and filter_word not in ["оплата"]:
                    return True
                # Если найдено слово "поквартально" или "квартальный" - точно True
                elif "квартал" in normal_word or "поквартал" in normal_word:
                    return True
    
    return False


# Пример
examples = [
    "Нужно актирование объектов по кварталам",       # True - содержит "актирование"
    "Произвели поквартальную оплату",                 # True - содержит "поквартальную"
    "Акты поквартально отправлены",                   # True - содержит "поквартально"
    "Просто ежемесячная оплата",                      # False - нет квартальных терминов
    'Поквартальная оплата'                            # True - содержит "поквартальная"
]

for e in examples:
    print(e, "->", oplata_filter(e))
