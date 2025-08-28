#!/usr/bin/env python3

from __future__ import annotations

import ast
import os
import json
import datetime

from yandex_cloud_ml_sdk import YCloudML
from dotenv import load_dotenv

load_dotenv()

AUTH_TOKEN = os.getenv('AUTH_TOKEN')
FOLDER_ID = os.getenv('FOLDER_ID')

sdk = YCloudML(
    folder_id=FOLDER_ID,
    auth=AUTH_TOKEN,
)

async def check_duration_and_deadline_gpt(text):
    """
    Проверяет текст вакансии и возвращает:
    - 'ДА', если нужно отсечь по продолжительности или дедлайну
    - 'НЕТ', если всё ок
    - 'УТОЧНИТЬ', если в вакансии нет ни продолжительности, ни дедлайна
    """
    current_date = datetime.date.today().strftime("%d.%m.%Y")
    messages = [
        {
            "role": "system",
            "text": f"""
            Проверь текст вакансии и верни один из трёх вариантов:
            - "ДА" → если нужно отсечь по хотя бы одному правилу.
            - "НЕТ" → если правила выполняются и всё в порядке.
            - "УТОЧНИТЬ" → если в вакансии вообще нет информации ни о продолжительности проекта, ни о дедлайне.

            Используй логику ИЛИ (OR) для отсечения.

            Правило 1 (Продолжительность): Отсечь, если продолжительность или срок проекта менее 3 месяцев. 
            Проекты должны быть от 3 месяцев и более.
            Примеры для отсева: "1 месяц", "2 мес", "до 2 месяцев", "менее 3 месяцев", "2 месяца", "от 2 месяцев" и т.п.
            Примеры для пропуска: "3 мес", "от 3 мес", "3+ мес", "4 мес", "от 6 мес", "6+ мес" и т.п.
            Если написано 'от 3х месяцев +' — НЕ отсекать (это подходит).

            Правило 2 (Дедлайн): Отсечь, если дедлайн в прошлом или сегодня. Сегодняшняя дата: {current_date}.

            ⚠️ Если в тексте вообще нет ни продолжительности, ни дедлайна — верни "УТОЧНИТЬ".
            """
        },
        {
            "role": "user",
            "text": text,
        },
    ]

    try:
        result = (sdk.models.completions("yandexgpt")
                  .configure(temperature=0.1)
                  .run_deferred(messages, timeout=60)
                  ).wait()
        return result.alternatives[0].text.strip()
    except Exception as e:
        print(f"Ошибка при проверке: {e}")
        return "УТОЧНИТЬ"

async def process_bonus_requirements_gpt(text: str) -> str:
    """
    Находит заголовки типа "Будет плюсом" и удаляет только их,
    оставляя текст под ними на месте.
    """
    messages = [
        {
            "role": "system",
            "text": """
            Твоя задача — найти в тексте вакансии определённые заголовки и удалить **только строку с заголовком**, оставив весь последующий текст без изменений.

            1.  **Найди строки**, которые полностью или частично соответствуют одному из следующих заголовков (могут содержать двоеточие или эмодзи ➕):
                * `Будет плюсом`
                * `Плюсом будет`
                * `Дополнительно`
                * `Доп. требования`
                * `Желательно`
                * `Приветствуется`

            2.  **Действие:** Удали **только** найденную строку с заголовком. Не трогай, не перемещай и не удаляй текст, который находится под этим заголовком.

            3.  **ВАЖНОЕ УСЛОВИЕ:** Если в тексте нет ни одного из этих заголовков, верни исходный текст без каких-либо изменений. Сохраняй все переносы строк и абзацы.
            """
        },
        {
            "role": "user",
            "text": text,
        },
    ]
    try:
        result = (sdk.models.completions("yandexgpt").configure(temperature=0.1).run_deferred(messages, timeout=120)).wait()
        return result.alternatives[0].text
    except Exception as e:
        print(f"Ошибка при удалении заголовков 'Будет плюсом': {e}")
        return text # В случае ошибки возвращаем исходный текст    
     # В случае ошибки возвращаем исходный текст
async def del_contacts_gpt(text):
    """
    Основная функция обработки текста вакансии.
    Выполняет очистку, извлечение данных и форматирование.
    """
    messages = [
        {
            "role": "system",
            "text": """
            Ты — фильтр вакансий.
            На вход тебе дается текст вакансии. Твоя задача — проанализировать его, отфильтровать и извлечь данные в формате JSON.

            ### Этап 1: Фильтрация
            Если вакансия не проходит хотя бы по одному из правил ниже → верни null.

            **Локация:**
            * ✅ **Проходит**, если: указано "РБ", "РБ" с другими странами, "Дружественные страны" (включая Беларусь), "Любые", "Без ограничений", 'РФ (предпочтительно)'.
            * ❌ **Отсекается**, если: только "РФ"/"Россия", перечень стран без РБ, или указано "кроме РБ".
            * Если в вакансии указано "РФ (предпочтительно)", считать подходящим.
            **Гражданство:**
            * ✅ **Проходит**, если: "РБ", "РФ", "Дружественные страны" (включая Беларусь), "Любые", "Без ограничений", "Без разницы".
            * ❌ **Отсекается**, если: указаны страны, исключающие РБ, или "кроме РБ".

            **Условия оплаты:**
            * ❌ **Отсекается**, если: оплата > 35 рабочих дней или > 50 календарных дней, либо есть фразы "акты поквартально", "поквартальное актирование", "квартальная оплата", "актирование".
            * ❌ **Отсекается**, если в тексте есть слово "стоп" или "СТОП".

            ### Этап 2: Извлечение данных и очистка (если вакансия прошла фильтрацию)

            **1. Контакты:**
            * Найди блок "Вопросы и предложения ➡️@username...". Замени его на "Вопросы и предложения пишите Дмитрию ➡️@Dimitryver. Указать 🆔 запроса.".
            * Удали все остальные контакты: Telegram (@...), телефоны, email, ссылки.
            * **ОБЯЗАТЕЛЬНО СОХРАНИТЬ информацию об оформлении (например, "Оформление:", "Оформление в РЛ на минимальную ставку" и т.п.) в тексте.**
            **2. Заголовок (`vacancy_title`):**
            2. Заголовок (`vacancy_title`):
          * Если в начале есть строка-заголовок (например, "🥇 Java разработчик..."), удали её из текста и верни в ключ "vacancy_title" (с сохранением всех символов, включая эмодзи и пробелы). Если нет — null.

            **3. ID Вакансии (`vacancy_id`):**  
            * Найди первый ID формата **"🆔 XX-1234", "🆔 8581", "XX-1234", "8581", "1с 8474" или "1с 1234"**.. Удали его из текста и верни значение в ключ "vacancy_id" без символа 🆔. Удали его из текста и верни значение в ключ "vacancy_id" (без "🆔"). Если нет — null.

            **4. Ставка (`rate`):**
            * Найди ставку. Если есть ставка для РФ и не для РФ, бери для не РФ. Верни только число. Если ставки нет — верни 0.
            * Полностью удали из текста все строки или фрагменты строк, где упоминаются:
            - "Ставка закупки"
            - "Ставка"
            - "Условия оплаты"
            - "Оплата"
            - "Отсрочка"
            - "Актирование"
            - числа в днях (например: "35 р.д.", "50 календарных дней", "45 рабочих дней")
            * Эти строки или их части нужно удалить полностью.
            * ❗️ При этом обязательно сохранить всё, что связано с "Оформление" (например, "Оформление:", "Оформление в РЛ на минимальную ставку").


            **5. Дедлайн ('deadline_date', 'deadline_time'):**
            * Найди дедлайн "до DD.MM.YYYY HH:MM". Извлеки дату и время в соответствующие ключи. Если их нет — null.
            
            
            
            **6. Сохранение форматирования:**
            * ❗️ **КЛЮЧЕВОЕ ПРАВИЛО:** В итоговом поле "text" сохрани абсолютно все исходные переносы строк, абзацы и пустые строки, за исключением удаленных блоков. Не меняй порядок строк.

            ### Этап 3: Формат ответа
            Всегда возвращай словарь со всеми ключами. Если данных нет — значение должно быть null.

            {
              "text": "<очищенный текст вакансии с сохраненными абзацами>",
              "rate": "<число или 0>",
              "deadline_date": "DD.MM.YYYY" или null,
              "deadline_time": "HH:MM" или null,
              "vacancy_id": "<id или null>",
              "vacancy_title": "<заголовок или null>"
              "utochnenie": true или false
            }
            """
        },
        {
            "role": "user",
            "text": text,
        },
    ]

    try:
        result = (sdk.models.completions("yandexgpt")
                  .configure(temperature=0.1)
                  .run_deferred(messages, timeout=180)).wait()
        clean_text = result.alternatives[0].text.strip()
        

        # сначала пробуем JSON
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            # если не JSON, пробуем через ast
            try:
                return ast.literal_eval(clean_text)
            except Exception as e2:
                
                
                # Пытаемся извлечь JSON из текста, если он обернут в другой текст
                import re
                json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                if json_match:
                    try:
                        json_text = json_match.group(0)
                        print(f"Найден JSON блок: {repr(json_text)}")
                        return json.loads(json_text)
                    except json.JSONDecodeError as e3:
                        print(f"Ошибка парсинга извлеченного JSON: {e3}")
                
                return {
                    'text': None, 'rate': None, 'deadline_date': None,
                    'deadline_time': None, 'vacancy_id': None,
                    'vacancy_title': None, 'utochnenie': False
                }
    except Exception as e:
        print(f"Ошибка при обработке вакансии: {e}")
        return {
            'text': None, 'rate': None, 'deadline_date': None,
            'deadline_time': None, 'vacancy_id': None,
            'vacancy_title': None, 'utochnenie': False
        }

async def process_vacancy(text):
    """
    Главная функция, которая координирует проверку и обработку вакансии.
    """
    should_reject = await check_duration_and_deadline_gpt(text)

    if should_reject == 'ДА':
        print("Проект отсеян. Возвращаем None.")
        return {
            'text': None,
            'rate': None,
            'deadline_date': None,
            'deadline_time': None,
            'vacancy_id': None,
            'vacancy_title': None,
            'utochnenie': False
        }

    elif should_reject == 'УТОЧНИТЬ':
        print("Нет сроков/дедлайна. Отмечаем utochnenie=True.")
        processed_text = await process_bonus_requirements_gpt(text)
        result = await del_contacts_gpt(processed_text)
        result["utochnenie"] = True
        return result

    else:  # 'НЕТ'
        print("Проект подходит. Обрабатываем 'Будет плюсом'...")
        processed_text = await process_bonus_requirements_gpt(text)

        print("Продолжаем основную обработку.")
        result = await del_contacts_gpt(processed_text)
        result["utochnenie"] = False
        return result


# Пример использования (остается без изменений)
# Пример использования
# async def main():
#     vacancy_with_duration = """🆔 1001
# 🥇 Python Developer

# Длительность: 6 мес
# Дедлайн: до 31.12.2025 23:59

# Оформление: в РЛ на минимальную ставку
# Условия оплаты: 35 р.д.

# Вопросы и предложения ➡️@SomeContact
#     """

#     vacancy_without_duration = """🆔 1002
# 🥇 Frontend Developer

# О проекте:
# Разработка интерфейсов для внутренней системы

# Оформление: по договоренности
# Ставка закупки: 2000
#     """

#     vacancy_with_expired_deadline = """🆔 1003
# 🥇 Java Developer

# Дедлайн: до 01.05.2024 12:00
# Продолжительность: 12 мес

# Оформление: в РЛ
# Оплата: 50 календарных дней
#     """

#     print("\n=== Вакансия со сроком и дедлайном ===")
#     res1 = await process_vacancy(vacancy_with_duration)
#     print(res1)

#     print("\n=== Вакансия без сроков ===")
#     res2 = await process_vacancy(vacancy_without_duration)
#     print(res2)

#     print("\n=== Вакансия с просроченным дедлайном ===")
#     res3 = await process_vacancy(vacancy_with_expired_deadline)
#     print(res3)

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())