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




VACANCY_ID_REGEX = re.compile(
    r"(?:🆔\s*)?(?:[\w\-\u0400-\u04FF]+[\s\-]*)?(\d+)",
    re.IGNORECASE
)


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





########### ИЗВЛЕКАТЕЛЬ АЙДИ ###########
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
        print("text is empty")
        return None

    # 🔹 Новое: чистим разметку перед поиском
    text = _clean_markup(text)

    # 🟡 Берём первую непустую строку
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        print("lines is empty")
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

# невидимые/неразрывные пробелы
_ZW_RE = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060\u00A0]")
# markdown-зачёркивание ~~...~~ → оставляем содержимое
_MD_STRIKE_RE = re.compile(r"~~\s*(.*?)\s*~~", re.DOTALL)
# HTML-теги (на всякий) — удаляем
_HTML_TAG_RE = re.compile(r"</?\s*(?:s|del|strike|b|strong|i|em|u|code|pre|span|font)[^>]*>", re.IGNORECASE)

def _normalize_dashes(s: str) -> str:
    # en/em dash → обычный дефис
    return s.replace("\u2013", "-").replace("\u2014", "-")

def _clean_markup(text: str) -> str:
    s = text
    s = _ZW_RE.sub("", s)                 # 1) убрать невидимые
    s = _MD_STRIKE_RE.sub(r"\1", s)       # 2) раскрыть ~~зачёркивание~~
    s = _HTML_TAG_RE.sub("", s)           # 3) убрать HTML-теги
    s = _normalize_dashes(s)              # 4) нормализовать дефисы
    s = s.replace("🆔", "🆔 ")            # 5) немного нормализовать префикс
    s = re.sub(r"\s+", " ", s).strip()    # 6) сжать пробелы
    return s







########### ПАРСЕР ЦБ РФ ###########
import requests
from bs4 import BeautifulSoup

def parse_cb_rf():
    try:
        url = 'https://www.cbr.ru/currency_base/daily/'
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.banki.ru/products/currency/cb/",
            "X-Requested-With": "XMLHttpRequest"
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'class': 'data'}).find_all('tr')
        usd = table[16].find_all('td')[-1].text.replace(" ", "").replace(",", ".")
        eur = table[18].find_all('td')[-1].text.replace(" ", "").replace(",", ".")
        byn = table[7].find_all('td')[-1].text.replace(" ", "").replace(",", ".")
        return {'USD': float(usd), 'EUR': float(eur), 'BYN': float(byn)}
    except Exception as e:
        print(f"Error parsing cb_rf: {e}")
        return None
    
    
text = '''
🆔SA-8974
📅 Дата публикации: 18.09.2025 09:01

🥇 Fullstack аналитик (СА 60% БА 40%) (Senior)

💰 Месячная ставка (на руки) до:
- Ежемесячная выплата Штат/Контракт: 165 000 RUB
- С отсрочкой платежа "35 рабочих дней" после подписания акта (Актирование ежемесячно):
  ИП: 203 000 RUB,
  Самозанятый: 229 000 RUB

📍 Локация/Гражданство: любая
🏠 Формат работы: удалённо
🎓 Грейд: Senior
📆 Срок проекта: 6 месяцев
🚀 Старт проекта: ASAP

📌 О проекте:
Мы ищем системного-бизнес аналитика в команду управления закупочной ценой и себестоимостью. Вместе с командой необходимо заниматься доработкой систем хранения, расчета, анализа и согласования различных типов цен и их структуры. Сфера: ретейл

📎 Задачи:
— Собирать, анализировать и валидировать требования (ФТ,НФТ) к системам
— Проектировать решения для их реализации
— Проектировать интеграционные взаимодействия
— Декомпозировать и ставить задачи команде разработки(бэк, фронт, API, интеграции)
— Участвовать в разборе инцидентов, выявлять причины и предлагать их решения
— Взаимодействовать со смежными командами для реализации кросс-командных проектов
— Проектировать модели данных в рамках поставленной задачи
— Консультировать команды по возникающим вопросам на этапе разработки и тестирования
— Описывать бизнес-процессы в моделях «AS IS» и «TO BE»
— Проводить GAP-анализ
— Взаимодействовать с пользователями, заказчиками и другими стейкхолдерами для выявления их потребностей и сбора обратной связи
— Проводить обучение использованию системы
— Документировать бизнес-требования для нового функционала, описывать варианты использования и пользовательские истории
— Проводить agile ритуалы команды
— Участвовать в формировании и оценке гипотез по развитию продукта

💻 Требования:
— Опыт работы аналитиком от 5 лет
— Знание СУБД oracle, понимание процессов управления закупками
— Опыт самостоятельного ведения задачи от бизнес-требований до релиза
— Навык работы с инструментами: Postman, Swagger, KafkaUI, GitHub
— Умение определять DOR, DOD для задач/доработок/продукта
— Навыки сбора требований с помощью интервью, исследования систем, чтения документации
— Навык документирования требований в формате use cases/user story/технического задания
— Умение моделировать UML модели: Entity-Relation, Use case, Sequence
— Навык моделирования бизнес-процессов BPMN на аналитическом уровне
— Навык использования/проектирования интеграций REST
— Опыт использования/документирования API в спецификации OpenAPI (swagger), asyncAPI
— Опыт работы/навыки проектирования интеграций с брокерами Apache Kafka, RabbitMQ
— Опыт работы/навык проектирования БД в СУБД PostgreSQL, Oracle Database
— Навык написания сложных SQL скриптов
— Понимание работы монолитной/микросервисной архитектуры
— Опыт работы в областях управления закупками, переговоров с поставщиками, формирования ассортимента
— Опыт работы с системой ITSM
— Опыт работы с Platformeco, Node.JS
— Умение проведение пользовательских интервью и исследований
— Разработка и внедрение метрик эффективности продукта

❗️ Обязательные данные по кандидату при подаче:
● ФИО
● Страна + Город
● Дата рождения (не возраст, а дата)
● Электронная почта
● Образование (ВУЗ, год окончания, специальность)
● Грейд
● Ставка
● Чек-лист соответствия требованиям (ДА/НЕТ)!!!!!

Контакт для вопросов: Дмитрий @Dimitryver!!!!
'''    
print(extract_vacancy_id(text))