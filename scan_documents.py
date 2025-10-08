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
    Принимает JSON-строку или словарь Python и ВОЗВРАЩАЕТ
    структурированный отчет, содержащий Имя кандидата, "Таблицу соответствия" и "Итог".
    Если поле отсутствует, выводит '❌'.
    Автоматически удаляет маркеры блока кода ```json и ```.
    """
    processed_data = json_data
    output_lines = []  # Список для хранения всех строк отчета

    # --- Блок очистки входных данных ---
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

    # Вспомогательная функция для форматирования поля "ключ: значение"
    def format_field(key, value):
        val_str = value if value else "❌"
        return f"{key}: {val_str}"

    # --- КАНДИДАТ (только ФИО) ---
    output_lines.append("="*15 + " 👤 КАНДИДАТ " + "="*15)
    candidate = data.get("candidate", {})
    output_lines.append(format_field("ФИО", candidate.get('full_name')))


    # --- ТАБЛИЦА СООТВЕТСТВИЯ ---
    output_lines.append("\n" + "="*12 + " ✅ ТАБЛИЦА СООТВЕТСТВИЯ " + "="*12)
    compliance = data.get("compliance_check", {})
    status_map = { "Да": "✅", "Нет (требуется уточнение)": "❓", "Нет (точно нет)": "❌" }
    
    output_lines.append("\n 📎 Обязательные требования:")
    must_haves = compliance.get('must_have')
    if must_haves:
        for req in must_haves:
            icon = status_map.get(req.get('status'), '▫️')
            output_lines.append(f"    {icon} {req.get('requirement')}")
            output_lines.append(f"      └─ Комментарий: {req.get('comment')}")
    else:
        output_lines.append("    Требования не указаны.")

    output_lines.append("\n 📎 Будет плюсом:")
    nice_to_haves = compliance.get('nice_to_have')
    if nice_to_haves:
        for req in nice_to_haves:
            icon = status_map.get(req.get('status'), '▫️')
            output_lines.append(f"    {icon} {req.get('requirement')}")
            output_lines.append(f"      └─ Комментарий: {req.get('comment')}")
    else:
        output_lines.append("    Требования не указаны.")

    # --- ИТОГ ---
    output_lines.append("\n" + "="*17 + " 🏁 ИТОГ " + "="*17)
    summary = data.get("summary", {})
    if summary:
        output_lines.append(format_field("Вердикт", summary.get('verdict')))
        output_lines.append(format_field("Зарплатные ожидания", summary.get('salary_expectations')))
    output_lines.append("="*41)

    return "\n".join(output_lines)