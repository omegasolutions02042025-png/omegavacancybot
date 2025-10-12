import inspect
from collections import namedtuple
from db import get_next_sequence_number
from gpt_gimini import generate_hashtags_gemini
from aiogram import Bot
from datetime import datetime
import pytz
import json
import re

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
        r"\bиз\s*рф\b",
        r"\bлокац(?:ия|и)\s*[:\-]?\s*рф\b",
        r"\bлок:\s*рф\b",
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
	m_loc = re.search(r"локац(?:ия|и)\s*(?:специалиста)?\s*[:\-]?\s*(.+)", text_lower, flags=re.IGNORECASE)
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
    Проверяет, есть ли в тексте упоминания о длительности проекта менее 3 месяцев.
    Возвращает True, если найдены такие упоминания (вакансию нужно отсечь).
    Проекты должны быть от 3 месяцев и более.
    """
    import re
    text_lower = text.lower()

    # Паттерны с числами — ищем только "1" или "2" (менее 3 месяцев)
    numeric_patterns = [
        r':\s*(\d+)\s*(месяц|мес|месяца|месяцев)',  # Простой паттерн для ": X месяцев"
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:и\s*менее|или\s*менее|до)',
        r'от\s*(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:и\s*меньше|или\s*меньше)',
        r'менее\s*(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'до\s*(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'(\d+)\s*(месяц|мес|месяца|месяцев)\s*(?:максимум|макс)',
        r'продолжительность\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'продолжительность\s*проекта\s*:\s*(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'длительность\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'срок\s*(?:проекта)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'контракт\s*(?:на\s*)?(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'работа\s*(?:на\s*)?(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'занятость\s*(?:на\s*)?(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'период\s*(?:работы)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'время\s*(?:работы)?\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)',
        r'проект\s*(?:рассчитан)?\s*(?:на\s*)?(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'задача\s*(?:на\s*)?(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'сотрудничество\s*(?:на\s*)?(\d+)\s*(месяц|мес|месяца|месяцев)',
        r'временные\s*рамки\s*(?:от\s*)?(\d+)\s*(?:до\s*)?(\d+)?\s*(месяц|мес|месяца|месяцев)'
    ]

    for pattern in numeric_patterns:
        for match in re.findall(pattern, text_lower):
            nums = [int(x) for x in match if x.isdigit()]
            # Отсекаем только если есть числа меньше 3 (1 или 2 месяца)
            if any(n < 3 for n in nums):
                return True
            # Если максимальное число в диапазоне меньше 3, тоже отсекаем
            if nums and max(nums) < 3:
                return True

    # Явные упоминания коротких проектов (менее 3 месяцев)
    explicit_patterns = [
        r'проект\s+на\s*(?:1|2|один|два)\s*(?:месяц|мес|месяца|месяцев)',
        r'срок\s*:\s*(?:1|2)\s*(?:месяц|мес|месяца|месяцев)',
        r'длительность\s*:\s*(?:1|2)\s*(?:месяц|мес|месяца|месяцев)',
        r'продолжительность\s*:\s*(?:1|2)\s*(?:месяц|мес|месяца|месяцев)',
        r'до\s*(?:1|2)\s*(?:месяц|мес|месяца|месяцев)',
        r'менее\s*3\s*(?:месяц|мес|месяца|месяцев)',
        r'меньше\s*3\s*(?:месяц|мес|месяца|месяцев)',
        r'краткосрочный\s*(?:проект|контракт)',
        r'временная\s*(?:работа|занятость)',
        r'короткий\s*(?:проект|срок)',
        
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
Локация:  РБ
Тайм-зона проекта: мск

О проекте:
Описание проекта: * некоммерческий банк РФ
Дата старта проекта: ASAP
Продолжительность проекта : от 2 месяцев


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

print(is_russia_only_citizenship(text=text))


VACANCY_ID_REGEX = re.compile(
    r"(?:🆔\s*)?(?:[\w\-\u0400-\u04FF]+[\s\-]*)?(\d+)",
    re.IGNORECASE
)

def extract_vacancy_id_and_text(text: str):
    match = VACANCY_ID_REGEX.search(text)
    vacancy_id = match.group(1) if match else None
    clean_text = VACANCY_ID_REGEX.sub("", text).strip()
    return vacancy_id, clean_text


def remove_vacancy_id(text: str) -> str:
    """
    Удаляет первую строку, если она содержит ID вакансии
    (например: 🆔04100101, 🆔 QA-8955, QA-8955, DEV-102, 04100101),
    но не трогает дату и остальной текст.
    """
    lines = text.strip().splitlines()

    if not lines:
        return text.strip()

    # Проверяем первую строку на ID
    first_line = lines[0].strip()

    # Паттерн для ID: опциональный 🆔, буквы/цифры/дефисы, не дата
    id_pattern = re.compile(r"^(?:🆔\s*)?[\w\-]+$", re.IGNORECASE)

    if id_pattern.match(first_line):
        # Удаляем первую строку
        lines = lines[1:]

    clean_text = "\n".join(lines)

    # Убираем лишние пустые строки (максимум 2 подряд)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)

    return clean_text.strip()




async def send_mess_to_group(group_id: int, message: str, vacancy_id: str, bot: Bot):
    seq_num = await get_next_sequence_number()
    text = remove_vacancy_id(message)
    vacancy_id = vacancy_id[-4:]
    vacancy_id = f'{seq_num:04d}{vacancy_id}'
    pometka = f'"📨 Отправляйте резюме с пометкой «{vacancy_id} Ruby of Rails», пожелания по размеру заработной платы (на руки), форму трудоустройства/оформления, на e-mail: cv@omega-solutions.ru"'
    heashtegs_gpt = await generate_hashtags_gemini(text)
    heashegs = f'#vacancy #работа #job #remote #удалёнка #OmegaVacancy\n{heashtegs_gpt}\n#{vacancy_id}'
    text_for_message = f'🆔{vacancy_id}\n\n{text}\n\n{pometka}\n\n{heashegs}'
    await bot.send_message(group_id, text_for_message, parse_mode="HTML")
    
    

def get_message_datetime(msg, tz: str = "Europe/Moscow") -> str:
    """
    Возвращает дату и время отправки сообщения в формате DD.MM.YYYY HH:MM
    с учётом указанной таймзоны.

    :param msg: объект сообщения (msg.date — datetime в UTC)
    :param tz: строка с таймзоной (по умолчанию "Europe/Moscow")
    :return: строка с датой и временем
    """
    # Берём дату из сообщения (всегда UTC)
    utc_date = msg.date  

    # Переводим в локальную зону
    target_tz = pytz.timezone(tz)
    local_date = utc_date.astimezone(target_tz)

    return local_date.strftime("%d.%m.%Y %H:%M")

def get_vacancy_title(text: str) -> str | None:
    """
    Возвращает заголовок вакансии — строку, начинающуюся с 🥇.
    Пример:
    🥇 Аналитик Colvir (Middle+/Senior) → "Аналитик Colvir (Middle+/Senior)"
    """
    if not text:
        return None

    pattern = re.compile(r'^\s*🥇\s*(.+)$', re.MULTILINE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()

    return None


def format_candidate_json_str(raw_str: str) -> str:
    """
    Обрабатывает строку JSON (в том числе с ```json ``` или тройными кавычками),
    парсит её и возвращает красиво форматированный текст для Telegram с отступами.
    """
    # Убираем ```json и ``` по краям
    cleaned_str = re.sub(r'^```json\s*', '', raw_str.strip())
    cleaned_str = re.sub(r'```$', '', cleaned_str.strip())

    # Пробуем распарсить JSON
    try:
        candidate_json = json.loads(cleaned_str)
    except json.JSONDecodeError:
        return "❌ Ошибка: неверный формат JSON"

    # Формируем красивый текст
    name = candidate_json.get("name", "")
    surname = candidate_json.get("surname", "")
    verdict = candidate_json.get("final_verdict", "")
    justification = candidate_json.get("justification", "")

    text = f"👤 Кандидат: {name} {surname}\n"
    text += f"📌 Итоговое решение: {verdict}\n\n"

    # Обязательные навыки
    text += "🛠 Обязательные навыки:\n"
    for skill in candidate_json.get("comparison_results", {}).get("required_skills", []):
        requirement = skill.get("requirement", "")
        status = skill.get("status", "")
        comment = skill.get("comment", "")
        text += f"- {requirement} — {status}\n  {comment}\n\n"  # добавлен перенос между навыками

    # Дополнительные навыки
    plus_skills = candidate_json.get("comparison_results", {}).get("plus_skills", [])
    if plus_skills:
        text += "➕ Дополнительные навыки:\n"
        for skill in plus_skills:
            text += f"- {skill}\n"
        text += "\n"

    # Обоснование
    if justification:
        text += f"📝 Обоснование:\n{justification}\n"

    return text

def extract_vacancy_id(text: str) -> str | None:
    """
    Извлекает ID вакансии из текста.
    Поддерживает форматы:
      🆔04100101, QA-8955, DEV-102, BE-9075, 8823
      а также ссылки:
      https://t.me/omega_vacancy_bot?start=2431_BE-8968
    Возвращает ID в верхнем регистре (например, "BE-8968" или "8823").
    """
    if not text:
        return None

    # 🟡 Берём первую непустую строку
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return None
    first_line = lines[0]

    # 🟢 1. Ищем ID в начале первой строки (с любыми символами после)
    id_pattern = re.compile(
        r"^(?:🆔\s*)?([A-ZА-Я]{1,5}-?\d{3,6}|\d{3,6})",
        re.IGNORECASE
    )
    match = id_pattern.search(first_line)
    if match:
        return match.group(1).upper()

    # 🟢 2. Если не нашли — пробуем достать из ссылки (start=XXXX_BE-XXXX)
    link_pattern = re.compile(
        r"start=\d+[_-]([A-ZА-Я]{1,5}-?\d{3,6}|\d{3,6})",
        re.IGNORECASE
    )
    match = link_pattern.search(text)
    if match:
        return match.group(1).upper()

    return None

text = """BE-8968 (https://t.me/omega_vacancy_bot?start=2431_BE-8968)
📅 Дата публикации: 22.09.2025 11:37

🥇 Senior Fullstack разработчик Kotlin (Senior)

💰 Месячная ставка (на руки) до:
- Ежемесячная выплата Штат/Контракт: 132 000 RUB
- С отсрочкой платежа "Срок уточняется" после подписания акта (Актирование ежемесячно):
  ИП: 168 000 RUB,
  Самозанятый: 189 000 RUB

📍 Локация/Гражданство: РФ
🏠 Формат работы: удалённо
🎓 Грейд: Senior
📆 Срок проекта: бессрочно
🚀 Старт проекта: 2 недели после апрува

📌 О проекте:
DevX - интегрированная среда разработки, использование которой в несколько раз увеличит скорость вывода на рынок новых продуктов и сервисов.

📎 Задачи:

💻 Требования:
— Уверенное владение Kotlin
— Асинхронное программирование, конкурентность
— Написание unit и integration тестов (JUnit, Testcontainers)
— Работа с Gradle (Kotlin DSL)
— Уверенное знание TypeScript
— Опыт написания backend-приложений на Node.js / Express / tRPC
— Опыт работы с WebView, Electron или аналогами
— Опыт работы с серверными утилитами и CLI-инструментами на TypeScript
— Знание архитектурных паттернов (DI, модули, слой сервисов)
— Работа с WebSocket / SSE / EventBus
— Подключение к API и взаимодействие с backend-логикой на TypeScript
— Опыт разработки IDE-плагинов (JetBrains Platform SDK, VSCode API)
— Настройка CI/CD пайплайнов (GitHub Actions, GitLab CI)
— Работа с Docker, базовые знания DevOps-инфраструктуры

⚠️ Особые условия:
— Тайм-зона проекта: Мск
— Загрузка: фулл-тайм

❗️ Обязательные данные по кандидату при подаче:
● ФИО
● Страна + Город
● Дата рождения (не возраст, а дата)
● Электронная почта
● Образование (ВУЗ, год окончания, специальность)
● Грейд
● Ставка
● Чек-лист соответствия требованиям (ДА/НЕТ)

Контакт для вопросов: @amt2809
# """
print(extract_vacancy_id(text))