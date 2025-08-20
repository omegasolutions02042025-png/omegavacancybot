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
	Проверяет:
	- Гражданство: отсечь, если строго РФ/Россия без дружественных/разрешающих формулировок
	- Локация специалиста: отсечь, если строго РФ/Россия без дружественных/разрешающих формулировок
	Отсекаем, если ЛЮБОЙ из блоков строгий (OR), даже если в другом блоке указано "любой"/дружественные.
	"""
	text_lower = text.lower()

	# Ключевые слова
	friendly_keywords = [
		"рб", "беларусь", "казахстан", "армения", "киргизия", "кыргызстан",
		"узбекистан", "таджикистан", "азербайджан", "сербия", "турция", "снг", "еаэс",
		"рф/рб", "рф и рб", "рф либо рб", "рф, рб"
	]
	broad_allow_keywords = [
		"любой", "любая", "без ограничений", "any", "worldwide", "global",
		"любая локация", "любой регион", "без привязки"
	]
	strict_russia_patterns = [
		r"только\s*(?:рф|россия)",
		r"только\s*гражданство\s*рф",
		r"паспорт\s*рф\s*обязателен",
		r"налоговое\s*резидентство\s*рф\s*обязательно",
		r"жители\s*рф",
		r"из\s*рф",
		r"лок:\s*рф",
		r"оформление\s*в\s*рф"
	]

	def contains_any(segment: str, keywords: list[str]) -> bool:
		return any(kw in segment for kw in keywords)

	def has_strict_russia(segment: str) -> bool:
		# Явные строгость/обязательность
		for p in strict_russia_patterns:
			if re.search(p, segment):
				return True
		# Просто упоминание РФ/Россия БЕЗ дружественных/разрешающих формулировок — считаем строгим
		if re.search(r"\bрф\b|\bроссия\b", segment):
			if not contains_any(segment, friendly_keywords) and not contains_any(segment, broad_allow_keywords):
				return True
		return False

	def segment_is_strict(segment: str) -> bool:
		# Если явно дружественные/разрешающие — не строгий
		if contains_any(segment, friendly_keywords) or contains_any(segment, broad_allow_keywords):
			return False
		# Иначе проверяем строгость РФ
		return has_strict_russia(segment)

	strict_citizenship = False
	strict_location = False

	# 1) Гражданство
	m_cit = re.search(r"гражданство\s*[:\-]?\s*(.+)", text_lower, flags=re.IGNORECASE)
	if m_cit:
		strict_citizenship = segment_is_strict(m_cit.group(1))

	# 2) Локация специалиста
	m_loc = re.search(r"локация\s*специалиста\s*[:\-]?\s*(.+)", text_lower, flags=re.IGNORECASE)
	if m_loc:
		strict_location = segment_is_strict(m_loc.group(1))

	# Отсекаем, если любой блок строгий
	return strict_citizenship or strict_location



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
    Проверяет, есть ли в тексте упоминания о длительности проекта 3 месяца или менее.
    Возвращает True, если найдены такие упоминания (вакансию нужно отсечь).
    
    Args:
        text (str): Текст для проверки
        
    Returns:
        bool: True если найдена длительность <= 3 месяца, False если больше 3 месяцев
    """
    import re
    
    # Приводим текст к нижнему регистру для поиска
    text_lower = text.lower()
    
    # Паттерны для поиска длительности 3 месяца или менее
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
                if number <= 3:
                    return True
            elif len(match) == 3:  # Диапазон чисел + единица измерения
                try:
                    num1 = int(match[0])
                    num2 = int(match[1]) if match[1] else num1
                    # Если любое из чисел 3 или меньше, отсекаем
                    if num1 <= 3 or num2 <= 3:
                        return True
                except ValueError:
                    continue
    
    # Дополнительная проверка для явных упоминаний 3 месяцев или менее
    explicit_patterns = [
        r'3\s*\+\s*мес',
        r'от\s*(\d+)\s*(?:месяц|мес|месяца|месяцев)\s*\+', # Находит "от N месяцев +"
        r'от\s*3х\s*(?:месяц|мес|месяца|месяцев)\s*\+',
        r'от\s*(?:3|трех|трёх)\s*(?:месяц|мес|месяца|месяцев)\s*\+',
        r'проект\s+на\s*(?:1|2|3|один|два|три)\s*(?:месяц|мес|месяца|месяцев)',
        r'^(?:3|три)\s*(?:\+|plus)\s*(?:месяц|мес|месяца|месяцев)',
        r'проект\s+на\s+3\s*(?:месяц|мес|месяца|месяцев)',
        r'срок\s*:\s*3\s*(?:месяц|мес|месяца|месяцев)',
        r'длительность\s*:\s*3\s*(?:месяц|мес|месяца|месяцев)',
        r'продолжительность\s*:\s*3\s*(?:месяц|мес|месяца|месяцев)'
    ]
    
    for pattern in explicit_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False

text = """

RedLab Partners, [19.08.2025 11:52]
🆔 8695 

🥇 Разработчик Jira (Middle-/Middle+)

Стек:
Jira: Администрирование, кастомизация
Плагины: Tempo, BigPicture, ScriptRunner
Языки: Groovy (обязательно), Python/JS (плюс)
Интеграции: REST API, Webhooks
Грейд: Middle-/Middle+
Опыт в годах: 
Локация: РФ
Гражданство: Любое

О проекте:
Кастомизация и автоматизация Jira (Cloud/Server) для внутренних процессов компании

Задачи:
Настройка сложных workflow и dashboards
Разработка скриптов на Groovy (ScriptRunner)
Конфигурация плагинов (Tempo, BigPicture)
Создание кастомных отчетов и автоматизаций
Оптимизация производительности Jira
Клиент: [IT-компания/продуктовая разработка]
Старт: ASAP
Длительность: До конца года (с возможностью продления)

Оформление:
Тип занятости: Удалёнка
Ставка закупки:
Для резидентов РФ: до 2000
Для нерезидентов РФ: до 1800
Загрузка: Фулл-тайм
Условия оплаты:  35 р.д.

📌 Обязательные навыки:

✅ Глубокое знание Jira (Cloud/Data Center)
✅ Опыт с ScriptRunner (Groovy)
✅ Работа с Tempo, BigPicture
✅ Настройка сложных workflow/

➕ Плюсом:

🔹 Опыт с другими плагинами (e.g. Automation, Structure)
🔹 Знание REST API Jira
🔹 Базовый SQL (для кастомных отчетов)

📝 Как откликнуться:
Присылайте CV (Word/PDF) с пометками:
ФИО + локация
Опыт с ключевыми плагинами (Tempo/BigPicture — ДА/НЕТ)

Вопросы и предложения ➡️@iVvvvTvvvVi
Указать 🆔 запроса.

Вопросы и предложения ➡️@Lyayssan
"""

# print(check_project_duration(text=text))