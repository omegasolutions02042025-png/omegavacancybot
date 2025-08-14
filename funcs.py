# --- Обычные функции ---

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

    # нормализуем текст
    normal_text_words = [morph.parse(w)[0].normal_form for w in text.lower().split()]
    normal_text = " ".join(normal_text_words)

    # проверяем каждую фразу
    for phrase in filters_raw:
        normal_phrase = " ".join(morph.parse(w)[0].normal_form for w in phrase.lower().split())
        if normal_phrase in normal_text:
            return True
    return False


# Пример
examples = [
    "Нужно актирование объектов по кварталам",       # True
    "Произвели поквартальную оплату",                 # True
    "Акты поквартально отправлены",                   # True
    "Просто ежемесячная оплата",
    'Поквартальная оплата',
    'Акты поквартально',
    '''
🆔8629

🥇 Frontend

О кандидате:
Стек: в описании
Грейд: в описании
Опыт в годах: в описании
Локация специалиста: не важно
Тайм-зона проекта: мск
Гражданство: не важно

О проекте:
Описание проекта:* в описании
Название конечного клиента или отрасль: ритейл
Дата старта проекта: ASAP 
Продолжительность проекта (от 3х месяцев): длительный

Оформление:
Тип занятости: удалёнка
Ставка закупки: смотри вашу
Загрузка: фулл-тайм 
Условия оплаты: поквартальная
Особые условия: -

Вопросы и предложения ➡️@katushar или в общий чат. Указать 🆔 запроса. 

❗️Обязательные данные по кандидату при подаче: ❗️
● ФИ
● Страна+Город
● Грейд
● Ставка
● Оценить требования ДА/НЕТ, в соответствии с наличием опыта.️
● ВСЕ ТРЕБОВАНИЯ ИЗ ЗАПРОСА ОТРАЖЕНЫ В ПРОЕКТАХ РЕЗЮМЕ

💻 Требования: 
Frontend-разработчик с уверенным владением JavaScript и TypeScript, со знанием React, Hooks, React Router, React Query, Vite, HTML5, современный CSS (Flex/Grid), CSS-модули.
❗️❗️❗️Продвинутые знания в области O365 (фреймворк SPFx, Active Directory, Power Automate)'''                       # False
]

for e in examples:
    print(e, "->", oplata_filter(e))
