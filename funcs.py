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

RedLab Partners, [19.08.2025 15:53]
🆔8496

❗️СМОТРЯТ БЫСТРО❗️

🥇 Разработчик full-stack  Middle

О кандидате:
Стек: 
Грейд: middle/middle+
Опыт в годах: минимум 3, лучше больше
Локация специалиста: РФ или СНГ
Тайм-зона проекта: Мск
Гражданство: РФ, СНГ

О проекте:
Название конечного клиента или отрасль: 
Дата старта проекта: ASAP 
Продолжительность проекта (от 3х месяцев): 

Оформление:
Тип занятости: удалёнка
Ставка закупки: смотрим ваши минимальные
Загрузка: фулл-тайм
Условия оплаты: 50 календарных дней 

Вопросы и предложения ➡️@katushar или в общий чат. Указать 🆔 запроса. 

❗️Обязательные данные по кандидату при подаче: ❗️
● ФИ
● Страна+Город
● Грейд
● Ставка
● Оценить требования ДА/НЕТ, в соответствии с наличием опыта.️
● ВСЕ ТРЕБОВАНИЯ ИЗ ЗАПРОСА ОТРАЖЕНЫ В ПРОЕКТАХ РЕЗЮМЕ

Ищем разработчика full-stack (или frontend) уровня middle  который должен разбираться в веб-разработке:

       —  backend на .net, 
       —  frontend на vite, stencil.js, typescript, ckEditor

➕Большим плюсом для frontend’a является знание библиотеки ckEditor. 
❗️Необходим ПРИКЛАДНОЙ опыт работы с библиотекой Stencil и редактором ckeditor. 
Кандидаты с богатым опытом работы с React также рассматриваются, однако наличие такого опыта будет рассматриваться как дополнительное преимущество
От специалиста потребуется  быстро разбираться с нестандартными задачами, реагировать на поступившие изменения.
"""

#print(check_project_duration(text=text))