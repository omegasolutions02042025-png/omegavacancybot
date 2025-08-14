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





def check_project_duration(text: str) -> bool:
    """
    Проверяет, есть ли в тексте упоминания о длительности проекта 4 месяца или менее.
    Возвращает True, если найдены такие упоминания (вакансию нужно отсечь).
    
    Args:
        text (str): Текст для проверки
        
    Returns:
        bool: True если найдена длительность <= 4 месяца, False если больше 4 месяцев
    """
    import re
    
    # Приводим текст к нижнему регистру для поиска
    text_lower = text.lower()
    
    # Паттерны для поиска длительности 4 месяца или менее
    patterns = [
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:и\s*менее|или\s*менее|до)',
        r'от\s*(\d+)\s*(?:до\s*)?(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:и\s*меньше|или\s*меньше)',
        r'менее\s*(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'до\s*(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:максимум|макс)',
        r'продолжительность\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'длительность\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'срок\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            # Обрабатываем разные форматы совпадений
            if len(match) == 2:  # Одно число + единица измерения
                number = int(match[0])
                if number <= 4:  # Изменено с <= 3 на <= 4
                    return True
            elif len(match) == 3:  # Диапазон чисел + единица измерения
                try:
                    num1 = int(match[0])
                    num2 = int(match[1]) if match[1] else num1
                    # Если любое из чисел 4 или меньше, отсекаем
                    if num1 <= 4 or num2 <= 4:  # Изменено с <= 3 на <= 4
                        return True
                except ValueError:
                    continue
    
    # Дополнительная проверка для явных упоминаний
    explicit_patterns = [
        r'4\s*(?:месяц|мес|месяца|месяцев)\s*(?:и\s*менее|или\s*менее|до)',
        r'менее\s*4\s*(?:месяц|мес|месяца|месяцев)',
        r'до\s*4\s*(?:месяц|мес|месяца|месяцев)',
        r'максимум\s*4\s*(?:месяц|мес|месяца|месяцев)',
        r'не\s*более\s*4\s*(?:месяц|мес|месяца|месяцев)',
        # Паттерны для точного "4 месяца" (отсечь)
        r'^4\s*(?:месяц|мес|месяца|месяцев)',  # В начале строки
        r'\s4\s*(?:месяц|мес|месяца|месяцев)\s',  # Между пробелами
        r'проект\s+на\s+4\s*(?:месяц|мес|месяца|месяцев)',  # "проект на 4 месяца"
        r'срок\s*:\s*4\s*(?:месяц|мес|месяца|месяцев)',  # "срок: 4 месяца"
        r'длительность\s*:\s*4\s*(?:месяц|мес|месяца|месяцев)',  # "длительность: 4 месяца"
        r'продолжительность\s*:\s*4\s*(?:месяц|мес|месяца|месяцев)'  # "продолжительность: 4 месяца"
    ]
    
    for pattern in explicit_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False

