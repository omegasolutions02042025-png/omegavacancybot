from docx import Document
from PyPDF2 import PdfReader
import pypandoc
from aiogram import Bot
import os
from gpt_gimini import sverka_vac_and_resume_json
import asyncio
from funcs import format_candidate_json_str
from striprtf.striprtf import rtf_to_text

# PDF → текст
def process_pdf(path: str) -> str:
    reader = PdfReader(path)
    text = []
    for page in reader.pages:
        text.append(page.extract_text() or "")
    return "\n".join(text)

# DOCX → текст
def process_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs])

# RTF → текст
def process_rtf(path: str) -> str:
    """
    Читает RTF-файл и возвращает чистый текст.
    Работает без Pandoc.
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    text = rtf_to_text(content)
    return text

# TXT → текст
def process_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

async def process_file_and_gpt(path: str, bot: Bot, user_id: int|str, vac_text: str):
    ext = path.split(".")[-1].lower()
    try:
        if ext == "pdf":
            text = process_pdf(path)
        elif ext == "docx":
            text = process_docx(path)
        elif ext == "rtf":
            text = process_rtf(path)
        elif ext == "txt":
            text = process_txt(path)
        else:
            await bot.send_message(user_id, f"⚠️ Формат {ext} не поддерживается: {path}")
            return
        
        text = asyncio.create_task(background_sverka(resume_text=text, vacancy_text=vac_text, bot=bot, user_id=user_id))
        
        os.remove(path)
    except Exception as e:
        await bot.send_message(user_id, f"❌ Ошибка в {path}: {e}")
        
        
async def background_sverka(resume_text: str, vacancy_text: str, bot: Bot, user_id: int|str):
    try:
        result = await asyncio.to_thread(sverka_vac_and_resume_json, vacancy_text, resume_text)
        
        if result:
            result = display_analysis(result)
            # Если результат большой, можно отправлять по частям
            for i in range(0, len(result), 4096):
                await bot.send_message(user_id, result[i:i+4096], parse_mode="HTML")
        else:
            await bot.send_message(user_id, "❌ Ошибка при сверке вакансии")
    except Exception as e:
        await bot.send_message(user_id, f"🔥 Ошибка при сверке: {e}")
        
        
        
        
        
        
import json

def display_analysis(json_data):
    """
    Принимает JSON-строку или словарь Python и выводит
    структурированный отчет по анализу кандидата.
    Автоматически удаляет маркеры блока кода ```json и ```.
    """
    processed_data = json_data

    # Блок очистки входных данных
    if isinstance(processed_data, str):
        # Убираем лишние пробелы и переносы по краям
        clean_str = processed_data.strip()
        # Если строка начинается с ```json, убираем эту часть
        if clean_str.startswith('```json'):
            clean_str = clean_str[len('```json'):].strip()
        # Если строка заканчивается на ```, убираем и это
        if clean_str.endswith('```'):
            clean_str = clean_str[:-len('```')].strip()
        
        try:
            # Пытаемся загрузить очищенную строку
            data = json.loads(clean_str)
        except json.JSONDecodeError:
            print("Ошибка: Некорректный формат JSON после очистки.")
            return
    else:
        # Если это уже словарь, работаем с ним напрямую
        data = processed_data

    def print_field(key, value, indent=0):
        prefix = " " * indent
        # Используем "не указано" для None или пустых строк
        val_str = value if value else "не указано"
        print(f"{prefix}{key}: {val_str}")

    # --- ВАКАНСЯ ---
    print("\n" + "="*15 + " 📝 ВАКАНСИЯ " + "="*15)
    vacancy = data.get("vacancy", {})
    if vacancy:
        pos_id = f"(ID: {vacancy.get('position_id')})" if vacancy.get('position_id') else ""
        print_field("Позиция", f"{vacancy.get('position_name')} {pos_id}")
        print_field("Грейд", vacancy.get('grade'))
        print_field("Формат работы", vacancy.get('work_format'))
        loc = vacancy.get('location_requirements', {})
        print_field("Требования к локации", f"Локация: {loc.get('location')}, Гражданство: {loc.get('citizenship')}, Пояс: {loc.get('timezone')}")
        print_field("Контакт", vacancy.get('manager_telegram_nickname'))
    
    # --- КАНДИДАТ ---
    print("\n" + "="*15 + " 👤 КАНДИДАТ " + "="*15)
    candidate = data.get("candidate", {})
    if candidate:
        print_field("ФИО", candidate.get('full_name'))
        b_date = candidate.get('birth_date', {})
        if b_date and b_date.get('date'):
            print_field("Дата рождения", f"{b_date.get('date')} ({b_date.get('age')})")
        loc = candidate.get('location', {})
        print_field("Локация", f"{loc.get('city')}, {loc.get('country')}")
        print_field("Позиция", candidate.get('grade_and_position'))

        print("\n  Опыт работы:")
        experience = candidate.get("experience")
        if experience:
            for exp in experience:
                print(f"    - Компания: {exp.get('company_name', 'не указано')} ({exp.get('period', 'N/A')})")
                print(f"      Должность: {exp.get('role', 'не указано')}")
                for proj in exp.get('projects', []):
                    print(f"      Проект: {proj.get('project_description', 'Описание отсутствует')}")
                    print("        Обязанности:")
                    for resp in proj.get('responsibilities', []):
                        print(f"          • {resp}")
        else:
            print("    Опыт работы не указан.")
        
        print("\n  Стек технологий:", ', '.join(candidate.get('tech_stack', [])) or "не указан")

    # --- ТАБЛИЦА СООТВЕТСТВИЯ ---
    print("\n" + "="*12 + " ✅ ТАБЛИЦА СООТВЕТСТВИЯ " + "="*12)
    compliance = data.get("compliance_check", {})
    status_map = {
        "Да": "✅",
        "Нет (требуется уточнение)": "❓",
        "Нет (точно нет)": "❌"
    }
    
    print("\n  Обязательные требования:")
    must_haves = compliance.get('must_have')
    if must_haves:
        for req in must_haves:
            icon = status_map.get(req.get('status'), '▫️')
            print(f"    {icon} {req.get('requirement')}")
            print(f"      └─ Комментарий: {req.get('comment')}")
    else:
        print("    Требования не указаны.")

    print("\n  Будет плюсом:")
    nice_to_haves = compliance.get('nice_to_have')
    if nice_to_haves:
        for req in nice_to_haves:
            icon = status_map.get(req.get('status'), '▫️')
            print(f"    {icon} {req.get('requirement')}")
            print(f"      └─ Комментарий: {req.get('comment')}")
    else:
        print("    Требования не указаны.")

    # --- ИТОГ ---
    print("\n" + "="*17 + " 🏁 ИТОГ " + "="*17)
    summary = data.get("summary", {})
    if summary:
        print_field("Вердикт", summary.get('verdict'))
        print_field("Зарплатные ожидания", summary.get('salary_expectations'))
    print("="*41)




