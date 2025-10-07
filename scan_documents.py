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

def display_analysis(json_data) -> str:
    
    processed_data = json_data
    if isinstance(processed_data, str):
        clean_str = processed_data.strip()
        if clean_str.startswith('```json'):
            clean_str = clean_str[len('```json'):].strip()
        if clean_str.endswith('```'):
            clean_str = clean_str[:-len('```')].strip()
        try:
            data = json.loads(clean_str)
        except json.JSONDecodeError:
            return "Ошибка: Некорректный формат JSON после очистки."
    else:
        data = processed_data

    lines = []

    def append_field(key, value, indent=0):
        prefix = " " * indent
        val_str = value if value else "не указано"
        lines.append(f"{prefix}{key}: {val_str}")

    # --- ВАКАНСИЯ ---
    lines.append("\n" + "="*15 + " 📝 ВАКАНСИЯ " + "="*15)
    vacancy = data.get("vacancy", {})
    if vacancy:
        pos_id = f"(ID: {vacancy.get('vacancy_id')})" if vacancy.get('vacancy_id') else ""
        append_field("Позиция", f"{vacancy.get('position')} {pos_id}")
        append_field("Грейд", vacancy.get("grade"))
        append_field("Формат работы", vacancy.get("format"))
        loc = f"Локация: {vacancy.get('location')}, Гражданство: {vacancy.get('citizenship')}, Пояс: {vacancy.get('timezone')}"
        append_field("Требования к локации", loc)
        append_field("Контакт", vacancy.get("manager_nick"))

    # --- КАНДИДАТ ---
    lines.append("\n" + "="*15 + " 👤 КАНДИДАТ " + "="*15)
    candidate = data.get("candidate", {})
    if candidate:
        append_field("ФИО", candidate.get("full_name"))
        append_field("Дата рождения", candidate.get("birth_date"))
        append_field("Локация", f"{candidate.get('city')}, {candidate.get('country')}")
        append_field("Позиция", candidate.get("position"))

        lines.append("\n  Опыт работы:")
        experience = candidate.get("experience", [])
        if experience:
            for exp in experience:
                lines.append(f"    - Компания: {exp.get('company_name', 'не указано')} ({exp.get('period', 'N/A')})")
                lines.append(f"      Должность: {exp.get('role', 'не указано')}")
                for proj in exp.get("projects", []):
                    lines.append(f"      Проект: {proj.get('description', 'Описание отсутствует')}")
                    lines.append("        Обязанности:")
                    for resp in proj.get("responsibilities", []):
                        lines.append(f"          • {resp}")
        else:
            lines.append("    Опыт работы не указан.")

        lines.append("\n  Стек технологий: " + ', '.join(candidate.get("tech_stack", [])) or "не указан")

    # --- ТАБЛИЦА СООТВЕТСТВИЯ ---
    lines.append("\n" + "="*12 + " ✅ ТАБЛИЦА СООТВЕТСТВИЯ " + "="*12)
    compliance = data.get("comparison_tables", {})
    status_map = {
        "Да": "✅",
        "Нет (уточнить)": "❓",
        "Нет (точно нет)": "❌"
    }

    lines.append("\n  Обязательные требования:")
    must_haves = compliance.get("must_have", [])
    if must_haves:
        for req in must_haves:
            icon = status_map.get(req.get("status"), '▫️')
            lines.append(f"    {icon} {req.get('requirement')}")
            lines.append(f"      └─ Комментарий: {req.get('comment')}")
    else:
        lines.append("    Требования не указаны.")

    lines.append("\n  Будет плюсом:")
    nice_to_haves = compliance.get("nice_to_have", [])
    if nice_to_haves:
        for req in nice_to_haves:
            icon = status_map.get(req.get("status"), '▫️')
            lines.append(f"    {icon} {req.get('requirement')}")
            lines.append(f"      └─ Комментарий: {req.get('comment')}")
    else:
        lines.append("    Требования не указаны.")

    # --- ИТОГ ---
    lines.append("\n" + "="*17 + " 🏁 ИТОГ " + "="*17)
    summary = data.get("candidate_result", {})
    if summary:
        append_field("Вердикт", summary.get("result_status"))
        append_field("Зарплатные ожидания", summary.get("salary_expectations"))

    lines.append("="*41)

    # Возвращаем готовый текст
    return "\n".join(lines)





