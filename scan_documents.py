from docx import Document
from PyPDF2 import PdfReader
import pypandoc
from aiogram import Bot
import os
from gpt_gimini import sverka_vac_and_resume_json, generate_mail_for_candidate_finalist, generate_mail_for_candidate_utochnenie, generate_mail_for_candidate_otkaz, generate_cover_letter_for_client
import asyncio
from funcs import format_candidate_json_str
from striprtf.striprtf import rtf_to_text
from db import add_otkonechenie_resume
from kb import utochnit_prichinu_kb

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
        
        text_gpt = await background_sverka(resume_text=text, vacancy_text=vac_text, bot=bot, user_id=user_id)
        
        os.remove(path)
    except Exception as e:
        await bot.send_message(user_id, f"❌ Ошибка в {path}: {e}")
    finally:
        return text_gpt or None
        
async def background_sverka(resume_text: str, vacancy_text: str, bot: Bot, user_id: int|str):
    try:
        result_gpt = await sverka_vac_and_resume_json(resume_text, vacancy_text)
        
        if result_gpt:
            result = display_analysis(result_gpt)
            result_gpt = clean_json(result_gpt)
            mail = await create_mails(result_gpt)
            verdict = result_gpt.get("summary").get("verdict")
            candidate = result_gpt.get("candidate").get("full_name")
            if verdict == "Не подходит":
                mes = await bot.send_message(user_id, f"❌ Кандидат {candidate} не подходит", reply_markup=utochnit_prichinu_kb())
                await add_otkonechenie_resume(mes.message_id, result)
                return mail
            # Если результат большой, можно отправлять по частям
            for i in range(0, len(result), 4096):
                await bot.send_message(user_id, result[i:i+4096], parse_mode="HTML")
            
            return mail
        else:
            await bot.send_message(user_id, "❌ Ошибка при сверке вакансии")
    except Exception as e:
        await bot.send_message(user_id, f"🔥 Ошибка при сверке: {e}")
        return None
    
    
        
        
        

import json


def clean_json(json_data):
    if isinstance(json_data, str):
        clean_str = json_data.strip()
        if clean_str.startswith('```json'):
            clean_str = clean_str[len('```json'):].strip()
        if clean_str.endswith('```'):
            clean_str = clean_str[:-len('```')].strip()
        
        try:
            data = json.loads(clean_str)
        except json.JSONDecodeError:
            return "Ошибка: Некорректный формат JSON после очистки."
    else:
        data = json_data
    return data

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
    processed_data = clean_json(processed_data)
    data = processed_data

    # Вспомогательная функция для форматирования поля "ключ: значение"
    def format_field(key, value):
        val_str = value if value else "❌"
        return f"{key}: {val_str}"

    # --- КАНДИДАТ (только ФИО) ---
    output_lines.append("="*15 + " 👤 КАНДИДАТ " + "="*15)
    candidate = data.get("candidate", {})
    output_lines.append(format_field("ФИО", candidate.get('full_name')))
    output_lines.append(format_field("—Дата рождения", candidate.get('birth_date').get('date')))
    
    output_lines.append(format_field("—Локация", candidate.get('location').get('city')))
    output_lines.append(format_field("—Стек технологий", ", ".join(candidate.get('tech_stack'))) )


    # --- ТАБЛИЦА СООТВЕТСТВИЯ ---
    output_lines.append("\n" + "="*12 + " ✅ ТАБЛИЦА СООТВЕТСТВИЯ " + "="*12)
    compliance = data.get("compliance_check", {})
    status_map = { "Да": "✅", "Нет (требуется уточнение)": "⚠️", "Нет (точно нет)": "❌" }
    
    must_haves = compliance.get('must_have')
    if must_haves:
        for req in must_haves:
            icon = status_map.get(req.get('status'), '▫️')
            output_lines.append(f"    {icon} {req.get('requirement')}")
    else:
        output_lines.append("    Требования не указаны.")


    nice_to_haves = compliance.get('nice_to_have')
    if nice_to_haves:
        for req in nice_to_haves:
            icon = status_map.get(req.get('status'), '▫️')
            output_lines.append(f"    {icon} {req.get('requirement')}")
    else:
        output_lines.append("    Требования не указаны.")

    # --- ИТОГ ---
    output_lines.append("\n" + "="*17 + " 🏁 ИТОГ " + "="*17)
    summary = data.get("summary", {})
    if summary:
        output_lines.append(format_field("Вердикт", summary.get('verdict')))
    output_lines.append("="*41)

    return "\n".join(output_lines)




def create_finalists_table(finalists: list[dict]):
  """
  Создает таблицу финалистов в формате Markdown.

  Args:
    finalists: Список словарей, где каждый словарь представляет финалиста
               с ключами 'name', 'grade', 'location', 'stack', и 'salary'.

  Returns:
    Строка с таблицей в формате Markdown.
  """

  
  
  header = "| ФИО/ФИ | Грейд | Локация | Ключевой стек | Зарплатные ожидания |\n"
  separator = "|---|---|---|---|---|\n"
  body = ""
  for finalist in finalists:
    if isinstance(finalist, str):
      continue
    candidate = finalist.get("candidate", {})
    summary = finalist.get("summary", {})
    verdict = summary.get("verdict", "")
    if verdict == "Полностью подходит":
      body += f"| {candidate['full_name'] or '❌'} | {candidate['grade_and_position'] or '❌'} | {candidate['location']['city'] or '❌'} | {summary['salary_expectations'] or '❌'} |{summary['verdict'] or '❌'}\n"
    elif verdict == "Частично подходит (нужны уточнения)":
      body += f"| {candidate['full_name'] or '❌'} | {candidate['grade_and_position'] or '❌'} | {candidate['location']['city'] or '❌'} | {summary['salary_expectations'] or '❌'} |{summary['verdict'] or '❌'}\n"
    elif verdict == "Не подходит":
      body += f"| {candidate['full_name'] or '❌'} | {candidate['grade_and_position'] or '❌'} | {candidate['location']['city'] or '❌'} | {summary['salary_expectations'] or '❌'} |{summary['verdict'] or '❌'}\n"
  return header + separator + body





import csv

def create_candidates_csv(candidates: list[dict], filename: str = "candidates_report.csv"):
  """
  Создает CSV-файл с отчетом по кандидатам.

  Args:
    candidates: Список словарей, где каждый словарь представляет кандидата.
    filename: Имя создаваемого CSV-файла.
  """
  # Заголовки для CSV файла
  headers = ["ФИО", "Грейд и Позиция", "Город", "Зарплатные ожидания", "Вердикт"]

  try:
    # Используем with для автоматического закрытия файла
    # encoding='utf-8-sig' для корректного отображения кириллицы в Excel
    # newline='' для правильной обработки переносов строк
    with open(filename, mode='w', newline='', encoding='utf-8-sig') as csv_file:
      writer = csv.writer(csv_file)

      # 1. Записываем заголовки
      writer.writerow(headers)

      # 2. Проходим по списку кандидатов и записываем данные
      for item in candidates:
        # Пропускаем некорректные записи в списке (если это просто строка)
        if isinstance(item, str):
          continue

        # Безопасно извлекаем вложенные данные
        candidate_info = item.get("candidate", {})
        summary_info = item.get("summary", {})
        location_info = candidate_info.get("location", {})
        
        # Собираем данные для одной строки в CSV
        row = [
          candidate_info.get("full_name", "N/A"),
          candidate_info.get("grade_and_position", "N/A"),
          location_info.get("city", "N/A"),
          summary_info.get("salary_expectations", "N/A"),
          summary_info.get("verdict", "N/A")
        ]
        
        # Записываем строку в файл
        writer.writerow(row)
        
    print(f"✅ Файл '{filename}' успешно создан.")

  except Exception as e:
    print(f"❌ Произошла ошибка при создании файла: {e}")
    
    
    
async def create_mails(finalist: dict):
    try:
    
      if isinstance(finalist, str):
        return None
      candidate = finalist.get("candidate", {})
      summary = finalist.get("summary", {})
      verdict = summary.get("verdict", "")
      cover_letter = None
      if verdict == "Полностью подходит":
        res = await generate_mail_for_candidate_finalist(finalist)
        cover_letter = await generate_cover_letter_for_client(finalist)
        return [res, candidate.get('full_name'), cover_letter]
      elif verdict == "Частично подходит (нужны уточнения)":
        res = await generate_mail_for_candidate_utochnenie(finalist)
        #cover_letter = await generate_cover_letter_for_client(finalist)
        return [res, candidate.get('full_name'), cover_letter]
      elif verdict == "Не подходит":
        res = await generate_mail_for_candidate_otkaz(finalist)
        return [res, candidate.get('full_name'), cover_letter]
    except Exception as e:
      print(f"❌ Произошла ошибка при создании письма: {e}")
      return None