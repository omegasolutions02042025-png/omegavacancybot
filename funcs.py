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



import re

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
		"рф/рб", "рф и рб", "рф либо рб", "рф, рб",
		"рф/дружественные", "рф / дружественные", "рф- друшственные", "рф - дружественные",
		"рф и дружественные страны", "рф либо дружественные", "рф, дружественные"
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
    """
    import re
    text_lower = text.lower()

    # Паттерны с числами — ищем только "1", "2" или "3"
    numeric_patterns = [
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:и\s*менее|или\s*менее|до)',
        r'от\s*(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:и\s*меньше|или\s*меньше)',
        r'менее\s*(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'до\s*(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:максимум|макс)',
        r'продолжительность\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'длительность\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'срок\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)'
    ]

    for pattern in numeric_patterns:
        for match in re.findall(pattern, text_lower):
            nums = [int(x) for x in match if x.isdigit()]
            if any(n <= 3 for n in nums):
                return True

    # Явные упоминания "3 месяца"
    explicit_patterns = [
        r'3\s*\+\s*мес',
        r'от\s*3х\s*(?:месяц|мес|месяца|месяцев)\s*\+',
        r"\bот\s*(?:3|тр(?:е|ё)х)\s*(?:мес\.?|месяц(?:а|ев)?)\b",
        r'от\s*(?:3|трех|трёх)\s*(?:месяц|мес|месяца|месяцев)\s*\+',
        r'от\s*(?:3|трех|трёх)\s*(?:месяц|мес|месяца|месяцев)\b',
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

🆔BE-8636

Scala Developer

Месячная ставка(на руки) до: 168 400 RUB

О кандидате:

Грейд: Middle+ / Senior
Локация специалиста: РФ, Беларусь, Казахстан, Армения
Тайм-зона проекта: мск

О проекте:
Описание проекта: * некоммерческий банк РФ
Дата старта проекта: ASAP
Продолжительность проекта : от 5 мес+

Оформление:
Тип занятости: удалёнка
Загрузка: фулл-тайм
Особые условия: нужна личная почта кандидата для неймчека.
Рассматриваются кандидаты, которые последние 6 мес не подавались на проекты ТБанка

Вопросы и предложения пишите Дмитрию ➡️@Dimitryver. Указать 🆔 запроса.

📝Присылать СV + данные по кандидату:
 ФИО
 Дата рождения
 почта кандидата для неймчека
 Локация (город)
 Возможная дата старта на новый проект
Планы на отпуск в ближайшие 3 месяца
 Оценить требования ДА/НЕТ, в соответствии с наличием опыта.️

📌 Задачи:

💻 Требования:

- Опыт: не менее 2 лет коммерческой разработки для миддл+
- Знание основных паттернов программирования, включая функциональную парадигму
- Умение писать масштабируемый асинхронный код
- Знание фреймворков для разработки и тестирования (ZIO, Cats, ScalaTest)
- Опыт работы с реляционными БД (PostgreSQL)
- Опыт проектирования, разработки и интеграции REST / JSON-RPC
- Знание Git
- Опыт работы с Jira / Wiki

- Опыт работы с MongoDB, ElasticSearch, Kafka, Redis
- Опыт использования фреймворка / экосистемы ZIO
"""

print(check_project_duration(text=text))