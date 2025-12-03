import google.generativeai as genai 
import os
import json
import re
import logging
from maps_for_gpt import (
    ROLES_MAP, GRADE_MAP, PROGRAM_LANG_MAP, FRAMEWORKS_MAP, TECH_MAP,
    PRODUCT_INDUSTRIES_MAP, LANG_MAP, PORTFOLIO_MAP, WORK_TIME_MAP,
    WORK_FORM_MAP, AVAILABILITY_MAP, CONTACTS_MAP
)
from dotenv import load_dotenv
from scan_documents import process_pdf, process_docx, process_doc, process_rtf, process_txt
from aiogram import Bot
load_dotenv()
from db_basa_resume import *
from google_sheets_for_basa import *
from docx_generator import *
from datetime import datetime, timedelta
import random
import string
import shutil

# Отключаем логирование pdfminer и docx
logging.getLogger('pdfminer').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfinterp').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfpage').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfdocument').setLevel(logging.WARNING)
logging.getLogger('docx').setLevel(logging.WARNING)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def process_resume(text: str, file_name: str = "") -> dict | None:
    file_info = f"\nНазвание файла: {file_name}\n" if file_name else ""
    
    # Создаем строки с доступными значениями из всех мап
    grade_values = ', '.join(f'"{v}"' for v in GRADE_MAP.values())
    roles_values = ', '.join(f'"{v}"' for v in ROLES_MAP.values())
    prog_lang_values = ', '.join(f'"{v}"' for v in PROGRAM_LANG_MAP.values())
    frameworks_values = ', '.join(f'"{v}"' for v in FRAMEWORKS_MAP.values())
    tech_values = ', '.join(f'"{v}"' for v in TECH_MAP.values())
    industries_values = ', '.join(f'"{v}"' for v in PRODUCT_INDUSTRIES_MAP.values())
    lang_values = ', '.join(f'"{v}"' for v in LANG_MAP.values())
    portfolio_values = ', '.join(f'"{v}"' for v in PORTFOLIO_MAP.values())
    work_time_values = ', '.join(f'"{v}"' for v in WORK_TIME_MAP.values())
    work_form_values = ', '.join(f'"{v}"' for v in WORK_FORM_MAP.values())
    availability_values = ', '.join(f'"{v}"' for v in AVAILABILITY_MAP.values())
    contacts_values = ', '.join(f'"{v}"' for v in CONTACTS_MAP.values())
    
    prompt = f"""Твоя задача — выступить в роли умного парсера резюме. Ты должен извлечь информацию из предоставленного текста и структурировать её в JSON-формате, строго следуя приведённым ниже правилам и структурам.

**ЗОЛОТОЕ ПРАВИЛО: НИКАКИХ ДОМЫСЛОВ И ЛИШНЕЙ ИНФОРМАЦИИ!**
Если в тексте резюме нет какой-либо информации, значение соответствующего поля в JSON должно быть `null` или пустым (`{{}}`). Не придумывай данные.

---
**КЛЮЧЕВЫЕ ПРАВИЛА СОПОСТАВЛЕНИЯ ДАННЫХ:**

1.  **СТРОГОЕ СООТВЕТСТВИЕ СЛОВАРЯМ:** Для полей, представляющих собой словари с boolean-значениями (например, `grade`, `programmingLanguages`, `frameworks`, `technologies` и т.д.), ты должен действовать как нормализатор:
    * Найди в тексте резюме упоминание навыка, роли или характеристики (например, "питон", "Джанго", "мидл").
    * Сопоставь найденное значение с одним из **КАНОНИЧЕСКИХ** значений, перечисленных ниже.
    * В итоговый JSON включи **ТОЛЬКО** ключ из канонического списка.
    * **ЕСЛИ** в резюме указан навык, которого нет в соответствующем списке канонических значений, **ПРОСТО ИГНОРИРУЙ ЕГО**. Не добавляй в JSON ключ, которого нет в списке.
2. **ПЕРЕВОД ИМЕН И ГЕОГРАФИИ:**
    * ФИО (firstName, lastName, patronymic): Если в тексте найдено имя на одном языке (например, "Иван"), автоматически переведи его на другой ("Ivan") и заполни оба поля в словаре {{"ru": "Иван", "en": "Ivan"}}.
    * Страна и Город (location, city): Реализуй аналогичную логику. При нахождении "Россия", поле location должно стать {{"ru": "Россия", "en": "Russia"}}. При нахождении "Russia", поле location должно стать {{"ru": "Россия", "en": "Russia"}}. При нахождении "Moscow", поле city должно стать {{"ru": "Москва", "en": "Moscow"}}.При нахождении "Москва", поле city должно стать {{"ru": "Moscow", "en": "Москва"}}.

3.  **СПИСКИ ДОПУСТИМЫХ ЗНАЧЕНИЙ (КАНОНИЧЕСКИЕ ЗНАЧЕНИЯ):**
    * **Грейды (`grade`):** {grade_values}
    * **Должности/Специализации (`specialization`):** {roles_values}
    * **Языки программирования (`programmingLanguages`):** {prog_lang_values}
    * **Фреймворки (`frameworks`):** {frameworks_values}
    * **Технологии (`technologies`):** {tech_values}
    * **Отрасли (`projectIndustries`):** {industries_values}
    * **Иностранные языки (`languages`):** {lang_values}
    * **Портфолио (`portfolio`):** {portfolio_values}
    * **Формат работы (`workTime`):** {work_time_values}
    * **Форма трудоустройства (`workForm`):** {work_form_values}
    * **Доступность (`availability`):** {availability_values}
    * **Контакты (`contacts`):** {contacts_values}

---
**ТЕКСТ РЕЗЮМЕ ДЛЯ АНАЛИЗА:**
{text}
{file_info}
---



**СТРУКТУРА JSON ДЛЯ ЗАПОЛНЕНИЯ:**

**ОСНОВНАЯ ИНФОРМАЦИЯ:**
- `firstName`: Словарь с русским и английским вариантами имени.
- `lastName`: Словарь с русским и английским вариантами фамилии.
- `patronymic`: Словарь с русским и английским вариантами отчества.
- `grade`: Словарь, где ключи **строго** из списка {grade_values}. Пример: {{"Junior": true, "Middle": false}}.
- `totalExperience`: Общий опыт в IT в годах.Выводи только число.Например было "2 года" - стало 2
- `specialExperience`: Опыт в основной специализации. Формат: 'Python Developer - 5 лет'.Используй только значения из списка {roles_values}.
- `dateOfExit`: Дата выхода на новое место работы.

**ТЕХНИЧЕСКИЕ НАВЫКИ:**
- `programmingLanguages`: Словарь, где ключи **строго** из списка {prog_lang_values}.
- `frameworks`: Словарь, где ключи **строго** из списка {frameworks_values}.
- `technologies`: Словарь, где ключи **строго** из списка {tech_values}.
- `specialization`: Словарь, где ключи **строго** из списка {roles_values}.

**КОНТАКТНАЯ ИНФОРМАЦИЯ:**
- `location`: Страна.
- `city`: Город.
- `contacts`: Словарь со всеми найденными контактами (phone, email, telegram, linkedin, github и т.д.).

**ПРОЧЕЕ:**
- `portfolio`: Словарь, где ключи **строго** из списка {portfolio_values}.
- `languages`: Словарь с иностранными языками и их уровнем. Ключи **строго** из списка {lang_values}. Если язык указан на русском (Например "английский") перевди на английский("English") согласно  {lang_values}.
- `projectIndustries`: Словарь, где ключи **строго** из списка {industries_values}.

**УСЛОВИЯ РАБОТЫ:**
- `availability`: Словарь, где ключи **строго** из списка {availability_values}.
- `workTime`: Словарь, где ключи **строго** из списка {work_time_values}.
- `workForm`: Словарь, где ключи **строго** из списка {work_form_values}.
- `salaryExpectations`: Словарь с суммой и валютой (`amount`, `currency`). Валюты: RUB, USD, EUR, BYN. Проверяй текст и название файла. "у.е." всегда USD. Числа в названии файла (например, "от 200000") — это зарплата в RUB.
- `rateRub`: Рейт в рублях.
**Пример JSON-структуры:**
```json
{{
  "specialization": {{"Python Developer": true, "Backend Developer": true}},
  "firstName": {{"ru": "Иван", "en": "Ivan"}},
  "lastName": {{"ru": "Иванов", "en": "Ivanov"}},
  "patronymic": {{"ru": "Иванович", "en": "Ivanovich"}},
  "grade": {{"Senior": true, "Middle": false, "Junior": false}},
  "totalExperience": "2",
  "dateOfExit": "2025-08-30",
  "specialExperience": "Python Developer - 5 лет",
  "programmingLanguages": {{"Python": true, "JavaScript": true, "TypeScript": true}},
  "frameworks": {{"Django": true, "FastAPI": true, "React": true}},
  "technologies": {{"PostgreSQL": true, "Docker": true, "AWS": true, "Redis": true}},
  "location": {{"ru": "Россия", "en": "Russia"}},
  "city": {{"ru": "Москва", "en": "Moscow"}},
  "contacts": {{
    "phone": "+79001234567",
    "email": "ivan.ivanov@example.com",
    "linkedin": "https://linkedin.com/in/ivanov",
    "telegram": "@ivanov_dev",
    "skype": "ivan.ivanov",
    "github": "https://github.com/ivanov",
    "gitlab": "https://gitlab.com/ivanov",
    "whatsapp": "+79001234567",
    "viber": "+79001234567",
    "discord": "ivanov#1234",
    "slack": "@ivanov",
    "microsoftTeams": "ivan.ivanov@company.com",
    "zoom": "ivan.ivanov@company.com",
    "googleMeet": "ivan.ivanov@gmail.com",
    "facebook": "https://facebook.com/ivan.ivanov",
    "instagram": "@ivanov_dev",
    "twitter": "@ivanov_dev",
    "vk": "https://vk.com/ivanov",
    "tiktok": "@ivanov_dev",
    "reddit": "u/ivanov_dev",
    "stackoverflow": "https://stackoverflow.com/users/123456/ivanov",
    "habrCareer": "https://career.habr.com/ivanov"
  }},
  "portfolio": {{"GitHub": "https://github.com/ivanov", "Medium": "https://medium.com/ivanov", "Personal Website": null}},
  "languages": {{"English": "B2", "Spanish": "A2", "German": null}},
  "projectIndustries": {{"FinTech": true, "Healthcare": true, "E-commerce": false}},
  "availability": {{"Open to offers": true, "Not looking": false}},
  "workTime": {{"Full-time": true, "Part-time": false, "Contract": false}},
  "workForm": {{"Оформление в штат": true, "B2B contract": true, "Самозанятый": false}},
  "salaryExpectations": {{"amount": "300000", "currency": "RUB"}},
  "rateRub": "1500"
}}


```"""

    
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    try:
        # Добавляем таймаут для GPT запроса
        import asyncio
        response = await asyncio.wait_for(
            model.generate_content_async(prompt),
            timeout=120.0  # 2 минуты таймаут
        )
        
        if response is None:
            print("❌ Ошибка: Gemini API вернул None")
            return None
        
        response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
    except asyncio.TimeoutError:
        print("❌ Таймаут при вызове Gemini API (120 секунд)")
        return None
    except AttributeError as e:
        print(f"❌ Ошибка при вызове Gemini API (AttributeError): {e}")
        print("🔄 Попытка использовать синхронный метод...")
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(model.generate_content, prompt),
                timeout=120.0
            )
            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        except asyncio.TimeoutError:
            print("❌ Таймаут при синхронном вызове Gemini API")
            return None
    except Exception as e:
        print(f"❌ Неожиданная ошибка при вызове Gemini API: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None

    try:
        response_json = json.loads(response_text)
        
        return response_json
    except json.JSONDecodeError:
        print(f"Ошибка при разборе JSON: {response_text}")
        return None



async def ensure_dict(d):
    return d if isinstance(d, dict) else {}

async def save_resume_in_db(files, username, user_dir) -> None:
    print(f"🔄 Начинаем обработку {len(files)} файлов для пользователя {username}")
    
    for file_name, path in files:
        ext = path.split(".")[-1].lower()
        print(f"📄 Обрабатываем файл: {file_name} ({ext})")
        
        # Проверяем, существует ли файл
        if not os.path.exists(path):
            print(f"❌ ФАЙЛ НЕ НАЙДЕН: {path}")
            print(f"📁 Проверяем папку: {os.path.dirname(path)}")
            if os.path.exists(os.path.dirname(path)):
                files_in_dir = os.listdir(os.path.dirname(path))
                print(f"📋 Файлы в папке: {files_in_dir}")
            else:
                print(f"❌ Папка не существует: {os.path.dirname(path)}")
            continue
            
        print(f"✅ Файл найден: {path}")

        try:
            import asyncio
            # Обработка документа в отдельном потоке
            if ext == "pdf":
                print(f"📖 Извлекаем текст из PDF: {file_name}")
                text = await asyncio.to_thread(process_pdf, path)
            elif ext == "docx":
                print(f"📖 Извлекаем текст из DOCX: {file_name}")
                text = await asyncio.to_thread(process_docx, path)
            elif ext == "doc":
                print(f"📖 Извлекаем текст из DOC: {file_name}")
                text = await asyncio.to_thread(process_doc, path)
            elif ext == "rtf":
                print(f"📖 Извлекаем текст из RTF: {file_name}")
                text = await asyncio.to_thread(process_rtf, path)
            elif ext == "txt":
                print(f"📖 Извлекаем текст из TXT: {file_name}")
                text = await asyncio.to_thread(process_txt, path)
            else:
                print(f"⚠️ Формат {ext} не поддерживается: {path}")
                continue

            print(f"✅ Текст извлечен, длина: {len(text)} символов")
            print(f"🤖 Отправляем на обработку в GPT: {file_name}")
            resume_json = await process_resume(text, file_name)
            

            if resume_json is None:
                print("⚠️ process_resume вернул None, пропускаем файл")
                continue
            
            print(f"✅ GPT обработка завершена для: {file_name}")
            print(f"🆔 Генерируем ID кандидата...")
            candidate_id = await generate_random_id()
            print(f"🆔 ID кандидата: {candidate_id}")
            
            print(f"☁️ Загружаем в Google Drive: {file_name}")
            orig_url, resume_ru, resume_en = await add_resumes_to_google_drive(text, file_name, resume_json, path)
            print(f"☁️ Загрузка в Google Drive завершена")
            
            ADMIN_USERNAME = ['kupimancik']

            name_ru = (resume_json.get("firstName") or {}).get("ru")
            name_en = (resume_json.get("firstName") or {}).get("en")
            surname_ru = (resume_json.get("lastName") or {}).get("ru")
            surname_en = (resume_json.get("lastName") or {}).get("en")
            patronymic_ru = (resume_json.get("patronymic") or {}).get("ru")
            patronymic_en = (resume_json.get("patronymic") or {}).get("en")
            location_ru = (resume_json.get("location") or {}).get("ru")
            location_en = (resume_json.get("location") or {}).get("en")
            city_ru = (resume_json.get("city") or {}).get("ru")
            city_en = (resume_json.get("city") or {}).get("en")
            total_experience = str(resume_json.get("totalExperience")) if resume_json.get("totalExperience") is not None else None
            special_experience = resume_json.get("specialExperience", None)
            date_of_exit = resume_json.get("dateOfExit", None)
            url_for_origin_resume = orig_url
            url_for_form_res_ru = resume_ru
            url_for_form_res_en = resume_en
            recruter_username = username
            date_of_add = datetime.now() if username not in ADMIN_USERNAME else None
            date_add_admin = datetime.now() if username in ADMIN_USERNAME else None
            
            
            # Пары (dict_из_резюме, MAP_канонический)
            # предположим, ensure_dict и build_bool_row уже есть

            # Секции с булевыми значениями
            bool_sections = [
                ("roles",               await ensure_dict(resume_json.get("specialization")),   ROLES_MAP),
                ("grades",              await ensure_dict(resume_json.get("grade")),            GRADE_MAP),
                ("programming_langs",   await ensure_dict(resume_json.get("programmingLanguages")), PROGRAM_LANG_MAP),
                ("frameworks",          await ensure_dict(resume_json.get("frameworks")),       FRAMEWORKS_MAP),
                ("technologies",        await ensure_dict(resume_json.get("technologies")),     TECH_MAP),
                ("project_industries",  await ensure_dict(resume_json.get("projectIndustries")),PRODUCT_INDUSTRIES_MAP),
                ("work_time",           await ensure_dict(resume_json.get("workTime")),         WORK_TIME_MAP),
                ("work_form",           await ensure_dict(resume_json.get("workForm")),         WORK_FORM_MAP),
                ("availability",        await ensure_dict(resume_json.get("availability")),     AVAILABILITY_MAP),
            ]
            
            named_rows = {}  # { "roles": {...}, "grades": {...}, ... }

            # Обрабатываем булевы секции
            for section_name, data_dict, MAP in bool_sections:
                row = await build_bool_row(data_dict, MAP)
                named_rows[section_name] = row

    
            contacts_dict = await ensure_dict(resume_json.get("contacts"))
            contacts_row = await build_row_for_string_fields(contacts_dict, CONTACTS_MAP)
            named_rows["contacts"] = contacts_row
            
            languages_dict = await ensure_dict(resume_json.get("languages"))
            languages_row = await build_row_for_string_fields(languages_dict, LANG_MAP)
            named_rows["languages"] = languages_row
            
            portfolio_dict = await ensure_dict(resume_json.get("portfolio"))
            portfolio_row = await build_row_for_string_fields(portfolio_dict, PORTFOLIO_MAP)
            named_rows["portfolio"] = portfolio_row
            
            print(f"💾 Сохраняем в базу данных: {file_name}")
            result = await add_to_candidate_table(candidate_id = candidate_id, name_ru = name_ru, name_en = name_en, surname_ru = surname_ru, surname_en = surname_en, patronymic_ru = patronymic_ru, patronymic_en = patronymic_en, location_ru = location_ru, location_en = location_en, city_ru = city_ru, city_en = city_en, total_experience = total_experience, special_experience = special_experience, date_of_exit = date_of_exit, url_for_origin_resume = url_for_origin_resume, url_for_form_res_ru = url_for_form_res_ru, url_for_form_res_en = url_for_form_res_en, recruter_username = recruter_username, date_of_add = date_of_add, date_add_admin = date_add_admin)
            if result is None:
                print("❌ Резюме уже существует в БД")
                continue
            
            print(f"💾 Записываем дополнительные данные кандидата...")
            await create_candidate_and_write(named_rows, result)
            print(f"✅ Резюме {file_name} успешно обработано и сохранено в БД")

        except Exception as e:
            import traceback
            print(f"❌ Ошибка при обработке файла {path}: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            continue

    # НЕ удаляем директорию здесь - она будет удалена вызывающей функцией
    # после завершения всех асинхронных задач
    print(f"✅ Обработка завершена для {len(files)} файлов")
        





#===================
#Необходимые функции
#===================
async def generate_random_id():
    letter = random.choice(string.ascii_lowercase)  # случайная буква a-z
    number = random.randint(10000, 99999)           # случайное число 10000-99999
    return f"{letter}_{number}"

from typing import Dict, Any

async def build_bool_row(data: Dict[str, Any], MAP: Dict[str, str]) -> Dict[str, bool]:
    """
    Из data делает строку-флаги:
    — Все ключи из MAP → присутствуют в результате с True/False.
      Ключ результата = каноническое имя из MAP (value).
    — Любые ключи из data, которых нет в MAP → тоже добавляются и получают False.
    — Истина определяется просто: bool(value).

    :param data: входной словарь, напр. {"python": True, "Django": 1, "что-то левое": "да"}
    :param MAP: словарь нормализации, напр. {"python": "Python", "django": "Django"}
                (ключи MAP могут быть в любом регистре)
    :return: словарь вида {"Python": True, "Django": True, "что-то левое": False, ...}
    """
    data = data or {}

    # Нормализация: нижний регистр для сравнения, но запоминаем оригинал ключей data
    data_lower_to_orig = {k.lower(): k for k in data.keys()}
    data_norm = {k.lower(): v for k, v in data.items()}

    # MAP тоже в нижнем регистре; значение — канон (как хотим видеть ключ в результате)
    map_norm = {k.lower(): canon for k, canon in MAP.items()}

    result: Dict[str, bool] = {}

    # 1) Пробегаем все ключи из MAP → кладём канонические имена
    for k_lower, canon in map_norm.items():
        value = data_norm.get(k_lower, False)
        result[canon] = bool(value)

    # 2) Добавляем неизвестные ключи из data → False
    for k_lower, value in data_norm.items():
        if k_lower not in map_norm:
            # восстановим оригинальное написание ключа (как пришло в data)
            orig_key = data_lower_to_orig.get(k_lower, k_lower)
            # по требованию — ставим False
            result[orig_key] = False

    return result



async def build_row_for_string_fields(data: dict, MAP: dict) -> dict:
    """
    Возвращает {CanonName: value_or_None} для строковых полей (contacts, languages, portfolio).
    Пустые значения преобразуются в None, а не в False.
    """
    data_norm = {str(k).strip().lower(): v for k, v in data.items()}
    out = {}
    for key_lc, canon in MAP.items():
        value = data_norm.get(key_lc)
        # Преобразуем пустые строки и False в None
        if not value or value == "" or value is False:
            out[canon] = None
        else:
            out[canon] = str(value) if value else None
    return out



async def translate_name_to_english(russian_name: str) -> str:
    """Переводит русское имя на английский язык"""
    
    # Словарь для транслитерации русских имен
    name_translations = {
        # Мужские имена
        'александр': 'Alexander', 'алексей': 'Alexey', 'андрей': 'Andrey', 'антон': 'Anton',
        'артем': 'Artem', 'артур': 'Arthur', 'борис': 'Boris', 'вадим': 'Vadim',
        'валентин': 'Valentin', 'василий': 'Vasily', 'виктор': 'Victor', 'виталий': 'Vitaly',
        'владимир': 'Vladimir', 'владислав': 'Vladislav', 'вячеслав': 'Vyacheslav',
        'геннадий': 'Gennady', 'георгий': 'George', 'григорий': 'Gregory', 'данил': 'Danil',
        'даниил': 'Daniel', 'денис': 'Denis', 'дмитрий': 'Dmitry', 'евгений': 'Eugene',
        'егор': 'Egor', 'иван': 'Ivan', 'игорь': 'Igor', 'илья': 'Ilya',
        'кирилл': 'Kirill', 'константин': 'Konstantin', 'леонид': 'Leonid', 'максим': 'Maxim',
        'михаил': 'Mikhail', 'никита': 'Nikita', 'николай': 'Nikolay', 'олег': 'Oleg',
        'павел': 'Pavel', 'петр': 'Peter', 'роман': 'Roman', 'сергей': 'Sergey',
        'станислав': 'Stanislav', 'тимур': 'Timur', 'федор': 'Fedor', 'юрий': 'Yury',
        
        # Женские имена
        'александра': 'Alexandra', 'алина': 'Alina', 'алла': 'Alla', 'анастасия': 'Anastasia',
        'анна': 'Anna', 'валентина': 'Valentina', 'валерия': 'Valeria', 'вера': 'Vera',
        'виктория': 'Victoria', 'галина': 'Galina', 'дарья': 'Darya', 'екатерина': 'Ekaterina',
        'елена': 'Elena', 'елизавета': 'Elizaveta', 'жанна': 'Zhanna', 'ирина': 'Irina',
        'карина': 'Karina', 'кристина': 'Kristina', 'лариса': 'Larisa', 'людмила': 'Lyudmila',
        'марина': 'Marina', 'мария': 'Maria', 'наталья': 'Natalya', 'ольга': 'Olga',
        'полина': 'Polina', 'светлана': 'Svetlana', 'татьяна': 'Tatyana', 'юлия': 'Julia'
    }
    
    # Транслитерация фамилий и отчеств
    transliteration_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    
    name_lower = russian_name.lower().strip()
    
    # Проверяем, есть ли имя в словаре переводов
    if name_lower in name_translations:
        return name_translations[name_lower]
    
    # Если нет в словаре, используем транслитерацию
    result = ''
    for char in name_lower:
        if char in transliteration_map:
            result += transliteration_map[char]
        else:
            result += char
    
    # Делаем первую букву заглавной
    return result.capitalize()


async def create_new_resume(text, id):
  
  prompt  = f"""PROMPT: Expert Resume Formatter 🧠 Роль: Эксперт по форматированию и унификации резюме 

Ты — профессиональный специалист по оформлению и стандартизации резюме, обладающий опытом работы с международными IT-компаниями и HR-платформами. 
Твоя задача: взять любое резюме кандидата (на русском или английском языке) и преобразовать его в строго структурированное и визуально выверенное резюме, соответствующее корпоративному стилю.

⚠️ КРИТИЧЕСКИ ВАЖНО: НЕ ПРИДУМЫВАЙ И НЕ ДОБАВЛЯЙ ИНФОРМАЦИЮ, КОТОРОЙ НЕТ В ИСХОДНОМ РЕЗЮМЕ!
- Используй только ту информацию, которая есть в тексте резюме
- Не добавляй технологии, навыки, опыт работы или другие данные от себя
- Если какой-то информации нет в резюме - не включай эту секцию
- Переформатируй и структурируй только существующую информацию 

🎯 Цель: 

Создать аккуратно оформленное, двуязычное резюме, удобное для восприятия заказчиком (включая технических менеджеров и HR), в формате, пригодном для PDF, Word и печати. 

🎨 ВИЗУАЛЬНЫЙ СТИЛЬ ОФОРМЛЕНИЯ:

При создании резюме используй следующую цветовую схему и стили:
• Фон: Белый #FFFFFF  
• Основной текст: Чёрный #000000  
• Второстепенный текст: Серый #555555 (даты, города, названия компаний)  
• Заголовки секций: Голубой #4A90E2, ЗАГЛАВНЫМИ  
• Подзаголовки: Чёрный/тёмно-серый #333333  
• Акценты (технологии): Чёрный #000000, обычный шрифт  
• Разделители: Светло-серый #DDDDDD (лучше использовать отступы)  

ВАЖНО: В тексте резюме используй HTML-теги для стилизации:  
- <b color="#4A90E2">ЗАГОЛОВКИ СЕКЦИЙ</b> — голубой цвет, ЗАГЛАВНЫМИ  
- <font color="#555555">Второстепенный текст</font> — серый  
- Технологии — обычным чёрным шрифтом  

✅ ЧТО ДОЛЖНО БЫТЬ СДЕЛАНО 

1. 🔐 Анонимизация:  

Удалить:  
• Фамилию  
• Отчество  
• Телефон, email, Skype и другие контакты  
• Ссылки на соцсети (LinkedIn, GitHub и т.д.)  
• Адрес проживания (город и страна остаются)  
• Упоминания зарплатных ожиданий  

Оставить только:  
• Имя  
• ID кандидата в формате Имя (ID-{id})  

2. 📑 Обязательная структура финального резюме:  

Добавляй только те блоки, где есть содержимое.  

**ДЛЯ РУССКОЙ ВЕРСИИ:**  
<b color="#4A90E2">ИНФОРМАЦИЯ О КАНДИДАТЕ</b>  
<b color="#4A90E2">РЕЗЮМЕ</b>  
<b color="#4A90E2">НАВЫКИ</b>  
<b color="#4A90E2">ОПЫТ РАБОТЫ</b>  
<b color="#4A90E2">ОБРАЗОВАНИЕ</b>  
<b color="#4A90E2">СЕРТИФИКАТЫ</b>  
<b color="#4A90E2">ДОПОЛНИТЕЛЬНО</b>  

**ДЛЯ АНГЛИЙСКОЙ ВЕРСИИ:**  
<b color="#4A90E2">CANDIDATE INFO</b>  
<b color="#4A90E2">SUMMARY</b>  
<b color="#4A90E2">SKILLS</b>  
<b color="#4A90E2">WORK EXPERIENCE</b>  
<b color="#4A90E2">EDUCATION</b>  
<b color="#4A90E2">CERTIFICATIONS</b>  
<b color="#4A90E2">ADDITIONAL INFORMATION</b>  

ВСЕ ЗАГОЛОВКИ СЕКЦИЙ ДОЛЖНЫ БЫТЬ СИНИМИ (#4A90E2) И ЗАГЛАВНЫМИ БУКВАМИ!  

3. 🧠 Стандарты для каждого блока:  

📌 Информация о кандидате (русская версия):  

<b color="#4A90E2">ИНФОРМАЦИЯ О КАНДИДАТЕ</b>  

Имя (ID-{id})  
Грейд и специализация: Senior Salesforce Developer и т.д.  
Если должность размытая → Software Engineer (specialization not specified) — [Apex, SOQL, LWC]  
Локация: Минск, Беларусь, Remote и т.д.  

📌 Candidate Info (английская версия):  

<b color="#4A90E2">CANDIDATE INFO</b>  

English name (ID-{id}) — только английское имя!  
Grade and Specialization: Senior Salesforce Developer и т.д.  
If unclear → Software Engineer (specialization not specified) — [Apex, SOQL, LWC]  
Location: Minsk, Belarus, Remote и т.д.  

📌 Резюме (русская версия):  

<b color="#4A90E2">РЕЗЮМЕ</b>  

Абзац: опыт, ключевые технологии, специализация, сертификации, проекты.  

📌 Summary (английская версия):  

<b color="#4A90E2">SUMMARY</b>  

Paragraph: total experience, technologies, specialization, certifications, projects.  

📌 Навыки (русская версия):  

<b color="#4A90E2">НАВЫКИ</b>  

Языки и платформы: Apex, JavaScript, SOQL  
UI и фреймворки: LWC, Aura, SLDS  
Интеграции: REST, SOAP, Webhooks  
Инструменты: VS Code, Git, Jira  
CI/CD и DevOps: (если есть)  

📌 Skills (английская версия):  

<b color="#4A90E2">SKILLS</b>  

Languages & Platforms: Apex, JavaScript, SOQL  
UI & Frameworks: LWC, Aura, SLDS  
Integrations: REST, SOAP, Webhooks  
Tools: VS Code, Git, Jira  
CI/CD, Testing, DevOps: (if any)  

📌 Опыт работы (русская версия):  

<b color="#4A90E2">ОПЫТ РАБОТЫ</b>  

Должность — Компания  
<font color="#555555">Сроки | Локация</font>  
Описание проекта: (1–2 предложения)  
Отрасль: FinTech, Healthcare и т.д.  
Задачи и достижения: список  
Технологии: перечисли  

📌 Work Experience (английская версия):  

<b color="#4A90E2">WORK EXPERIENCE</b>  

Position — Company  
<font color="#555555">Period | Location</font>  
Project Description: (1–2 sentences)  
Industry: FinTech, Healthcare и т.д.  
Tasks and Achievements: bulleted list  
Technologies: list  

📌 Образование (русская версия):  

<b color="#4A90E2">ОБРАЗОВАНИЕ</b>  

Уровень, специальность, университет, страна, год  

📌 Education (английская версия):  

<b color="#4A90E2">EDUCATION</b>  

Level, specialty, university, country, year  

📌 Сертификаты (русская версия):  

<b color="#4A90E2">СЕРТИФИКАТЫ</b>  

Список с датами  

📌 Certifications (английская версия):  

<b color="#4A90E2">CERTIFICATIONS</b>  

List with dates  

📌 Дополнительно (русская версия):  

<b color="#4A90E2">ДОПОЛНИТЕЛЬНО</b>  

📌 Additional Information (английская версия):  

<b color="#4A90E2">ADDITIONAL INFORMATION</b>  

Languages: (с уровнями)  
Additional tools: open-source, mentoring, volunteering  

🌐 Перевод:  
Если резюме на русском → добавь английскую версию.  
Если резюме на английском → добавь русскую.  
В английской версии ни одного русского символа!  

ВАЖНО: Верни результат СТРОГО в формате JSON:
{{
  "russian": "полный текст резюме на русском языке с HTML-тегами для стилизации",
  "english": "полный текст резюме на английском языке с HTML-тегами для стилизации"
}}

Текст резюме: {text}

"""



  
  model = genai.GenerativeModel("gemini-2.5-flash")
  try:
    import asyncio
    response = await asyncio.wait_for(
        model.generate_content_async(prompt),
        timeout=120.0  # 2 минуты таймаут
    )
    response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
  except asyncio.TimeoutError:
    print("❌ Таймаут при создании нового резюме (120 секунд)")
    return {"russian": "Ошибка обработки резюме", "english": "Resume processing error"}
  except Exception as e:
    print(f"❌ Ошибка при создании нового резюме: {e}")
    return {"russian": "Ошибка обработки резюме", "english": "Resume processing error"}
  
  try:
    response_json = json.loads(response_text)
    
    # Исправляем цветовые значения в HTML-тегах
    if "russian" in response_json:
      response_json["russian"] = await fix_color_formatting(response_json["russian"])
    if "english" in response_json:
      response_json["english"] = await fix_color_formatting(response_json["english"])
      
      # Переводим русские имена на английский в английской версии
      english_text = response_json["english"]
      
      # Ищем русские имена в тексте и заменяем их на английские
      import re
      
      # Расширенный паттерн для поиска русских имен, фамилий и отчеств (кириллица)
      russian_name_pattern = r'\b[А-ЯЁ][а-яё]{1,}(?:\s+[А-ЯЁ][а-яё]{1,})*\b'
      
      # Находим все русские имена и заменяем их на английские
      matches = re.findall(russian_name_pattern, english_text)
      for russian_name in matches:
        if ' ' in russian_name:
          parts = russian_name.split()
          english_parts = []
          for part in parts:
            english_parts.append(await translate_name_to_english(part))
          english_name = ' '.join(english_parts)
        else:
          english_name = await translate_name_to_english(russian_name)
        english_text = english_text.replace(russian_name, english_name)
      
      response_json["english"] = english_text
    
    return response_json
  except json.JSONDecodeError:
    print(f"Ошибка при разборе JSON ответа create_new_resume: {response_text}")
    # Возвращаем fallback структуру с исправленными цветами
    fixed_text = await fix_color_formatting(response_text)
    return {
      "russian": fixed_text,
      "english": fixed_text
    }




async def fix_color_formatting(text: str) -> str:
    """Исправляет цветовые значения в HTML-тегах, добавляя # перед hex-кодами"""
    # Исправляем color="1F4E79" на color="#1F4E79"
    text = re.sub(r'color="([0-9A-Fa-f]{6})"', r'color="#\1"', text)
    # Исправляем color="555555" на color="#555555"
    text = re.sub(r'color="([0-9A-Fa-f]{3,6})"', r'color="#\1"', text)
    return text



async def add_resumes_to_google_drive(resume_text, candidate_id, resume_data, local_file_path):
    new_resume_data = await create_new_resume(resume_text, candidate_id)
    gm = GoogleDriveManager()
    
    # Извлекаем имя файла из пути
    file_name = os.path.basename(local_file_path)
    # Очищаем markdown символы из обеих версий и исправляем цветовые значения
    if isinstance(new_resume_data, dict):
        new_resume_russian = new_resume_data.get('russian', '')
        new_resume_english = new_resume_data.get('english', '')
        
        # Более аккуратная очистка markdown без повреждения кириллицы
        import re
        new_resume_russian = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', new_resume_russian)
        new_resume_russian = re.sub(r'#{1,6}\s*', '', new_resume_russian)
        new_resume_english = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', new_resume_english)
        new_resume_english = re.sub(r'#{1,6}\s*', '', new_resume_english)
        
        # Исправляем цветовые значения и убираем проблемные символы
        new_resume_russian = await fix_color_formatting(new_resume_russian)
        new_resume_english = await fix_color_formatting(new_resume_english)
        
        # Убираем символы ■ и другие проблемные символы
        new_resume_russian = new_resume_russian.replace('■', '').replace('\ufffd', '').replace('\u25a0', '')
        new_resume_english = new_resume_english.replace('■', '').replace('\ufffd', '').replace('\u25a0', '')
    else:
        # Fallback для старого формата
        new_resume_russian = str(new_resume_data)
        new_resume_english = new_resume_russian
        
        # Более аккуратная очистка markdown
        import re
        new_resume_russian = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', new_resume_russian)
        new_resume_russian = re.sub(r'#{1,6}\s*', '', new_resume_russian)
        new_resume_english = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', new_resume_english)
        new_resume_english = re.sub(r'#{1,6}\s*', '', new_resume_english)
        
        # Исправляем цветовые значения и убираем проблемные символы
        new_resume_russian = await fix_color_formatting(new_resume_russian)
        new_resume_english = await fix_color_formatting(new_resume_english)
        
        # Убираем символы ■ и другие проблемные символы
        new_resume_russian = new_resume_russian.replace('■', '').replace('\ufffd', '').replace('\u25a0', '')
        new_resume_english = new_resume_english.replace('■', '').replace('\ufffd', '').replace('\u25a0', '')
    if not resume_data:
        print("❌ Не удалось извлечь данные из резюме")
        return None, None, None
    
    print(f"✅ Данные извлечены!")
    
    
    
    first = (resume_data.get("firstName") or {}).get('ru')
    last = (resume_data.get("lastName") or {}).get('ru')
    first_en = (resume_data.get("firstName") or {}).get('en')
    last_en = (resume_data.get("lastName") or {}).get('en')
    

    if first and last:
        folder_name = f"{candidate_id}\n{first} {last}"
    elif first:
        folder_name = f"{candidate_id}\n{first}"
    elif last:
        folder_name = f"{candidate_id}\n{last}"
    else:
        folder_name = f"{candidate_id}\nРезюме"
    
    # Получаем или создаем папку
    folder_id = await gm.get_or_create_folder(folder_name)
    if not folder_id:
        print("❌ Не удалось отправить в Google Drive")
        return None, None, None
    # Загружаем файл и получаем результат с информацией о файле
    file_url = None
    upload_result = await gm.upload_file(
        file_path=local_file_path,
        folder_id=folder_id,
        file_name=local_file_path.split('/')[-1],
    )
    
    if upload_result and upload_result.get('success'):
        file_id = upload_result.get('file_id')
        file_url = upload_result.get('web_link')
        
        # Делаем файл общедоступным
        if file_id:
            permissions_set = await gm.set_file_permissions(file_id, permission_type='reader', role='anyone')
            if permissions_set:
                print(f"✅ Файл успешно загружен в Google Drive и сделан общедоступным!\n🔗")
            else:
                print(f"✅ Файл загружен в Google Drive, но не удалось сделать его общедоступным\n🔗")
        elif file_url:
            print(f"✅ Файл успешно загружен в Google Drive!\n🔗")
        else:
            print(f"✅ Файл успешно загружен в Google Drive!")
    else:
        error_msg = upload_result.get('error', 'Неизвестная ошибка') if upload_result else 'Не удалось загрузить файл'
        print(f"❌ Не удалось загрузить файл в Google Drive: {error_msg}")
    
    # Загружаем обработанные резюме как Word документы (русская и английская версии)
    new_resume_url_russian = None
    new_resume_url_english = None
    
    if new_resume_russian:
        # Загружаем русскую версию
        new_resume_filename_ru = f"Обработанное_RU_{file_name.replace('.pdf', '').replace('.docx', '')}"
        new_resume_title_ru = f"{first} {last}" if first and last else "Резюме (RU)"
        
        docx_upload_result_ru = await create_and_upload_docx_to_drive(
            text=new_resume_russian,
            file_name=new_resume_filename_ru,
            folder_name=folder_name,
            title=new_resume_title_ru,
            credentials_path="oauth.json"
        )
        
        if docx_upload_result_ru.get('success'):
            new_resume_url_russian = docx_upload_result_ru.get('web_link')
            print(f"✅ Русское резюме загружено в Word!\n🔗")
        else:
            print(f"⚠️ Не удалось загрузить русское резюме: {docx_upload_result_ru.get('error', 'Неизвестная ошибка')}")
    
    if new_resume_english:
        # Загружаем английскую версию
        new_resume_filename_en = f"Обработанное_EN_{file_name.replace('.pdf', '').replace('.docx', '')}"
        new_resume_title_en = f"{first_en} {last_en}" if first_en and last_en else "Resume (EN)"
        
        docx_upload_result_en = await create_and_upload_docx_to_drive(
            text=new_resume_english,
            file_name=new_resume_filename_en,
            folder_name=folder_name,
            title=new_resume_title_en,
            credentials_path="oauth.json"
        )
        
        if docx_upload_result_en.get('success'):
            new_resume_url_english = docx_upload_result_en.get('web_link')
            print(f"✅ Английское резюме загружено в Word!\n🔗")
        else:
            print(f"⚠️ Не удалось загрузить английское резюме: {docx_upload_result_en.get('error', 'Неизвестная ошибка')}")

    return file_url, new_resume_url_russian, new_resume_url_english





async def sverka_kandidate_in_basa(vacancy_text: str, candidates_text: str):
    promt = f"""
    Ты — система подбора IT-кандидатов. Твоя задача:

Взять текст вакансии и извлечь из него технический стек (языки, фреймворки, БД, облака, DevOps-инструменты, тестовые фреймворки и т.п.).

Взять список кандидатов (каждый кандидат содержит: id, fullName, techStack или skills) и сравнить стек вакансии со стеком каждого кандидата.

Посчитать процент совпадения для каждого кандидата.

Вернуть JSON со списком кандидатов, отсортированным по проценту совпадения по убыванию.

В JSON на каждого кандидата вывести:

fullName — ФИО кандидата

percent — процент совпадения (целое число 0–100)

id — id кандидата (как в исходных данных)

Входные данные

Я буду давать тебе в одном сообщении два блока:

VACANCY: — текст вакансии {vacancy_text}

CANDIDATES: — список кандидатов {candidates_text}

Пример формата входа:

VACANCY:
Ищем Senior Java Developer. Стек: Java 17, Spring Boot, Hibernate, PostgreSQL, Kafka, Docker, Kubernetes, Git, Jenkins, REST, микросервисы.

CANDIDATES:
1) id: c_101, fullName: "Иван Петров", techStack: "Java, Spring, Spring Boot, Hibernate, PostgreSQL, MongoDB, Docker"
2) id: c_102, fullName: "Sergey Sidorov", techStack: "Kotlin, Java, Micronaut, Kafka, PostgreSQL, Git, CI/CD"
3) id: c_103, fullName: "Anna Dev", techStack: "Python, Django, PostgreSQL"

Правила извлечения стека вакансии

Извлекай только технологии, а не «soft skills», не «опыт от 3 лет», не «английский».

Считай за технологии: языки (Java, Kotlin, Python…), фреймворки (Spring, Django…), БД (PostgreSQL, MySQL, MongoDB…), брокеры (Kafka, RabbitMQ), DevOps (Docker, Kubernetes, Jenkins, GitLab CI), облака (AWS, GCP, Azure), API (REST, gRPC).

Нормализуй написание: Postgres → PostgreSQL, K8s → Kubernetes, JS → JavaScript, TS → TypeScript.

Если в вакансии указано семейство (например, "Spring") и у кандидата "Spring Boot" — засчитывай как совпадение.

Как считать процент совпадения

Сначала сформируй множество технологий вакансии V.

Для кандидата сформируй множество технологий кандидата C.

Совпадение = (кол-во технологий из V, которые есть в C) / (кол-во технологий в V) * 100.

Округляй до целого.

Если у кандидата вообще нет техстека — процент = 0.

Если кандидат указал технологию более конкретно (вакансия: Spring, кандидат: Spring Boot) — считай как совпадение.

Если технологию можно считать эквивалентной (например, CI/CD в кандидате и Jenkins в вакансии) — засчитывай 1 совпадение.

Не придумывай технологии, которых нет в данных.

Формат ответа

Ответ всегда в формате JSON, без пояснений, без маркдауна, без комментариев.

Структура:

{{
  "vacancy_stack": ["Java", "Spring Boot", "Hibernate", "PostgreSQL", "Kafka", "Docker", "Kubernetes", "Git", "Jenkins", "REST"],
  "candidates": [
    {{
      "fullName": "Иван Петров",
      "percent": 90,
      "id": "c_101"
    }},
    {{
      "fullName": "Sergey Sidorov",
      "percent": 80,
      "id": "c_102"
    }},
    {{
      "fullName": "Anna Dev",
      "percent": 20,
      "id": "c_103"
    }}
  ]
}}


Требования:

candidates — отсортирован по percent по убыванию.

Все проценты — целые.

Если кандидат не совпал — тоже включи его, но с 0.

Имена и id бери ровно из входных данных."""
    

    import json
  
    model = genai.GenerativeModel("gemini-2.5-flash")
    generation_config = genai.types.GenerationConfig(temperature=0.1, response_mime_type='application/json')
    response = await model.generate_content_async(promt, generation_config=generation_config)

    print(type(response.text))
   
    res = json.loads(response.text)
    print(type(res))
    return res
  







async def main():
    """Основная функция для тестирования"""
    print("Модуль redact_resume загружен успешно")
    print("Все функции готовы к использованию")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())





