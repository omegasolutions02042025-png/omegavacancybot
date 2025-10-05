from docx import Document
from PyPDF2 import PdfReader
import pypandoc
from aiogram import Bot
import os
from gpt_gimini import sverka_vac_and_resume
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
    return pypandoc.convert_text(open(path, encoding="utf-8").read(), "plain", format="rtf")

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
        try:
            text = await sverka_vac_and_resume(resume_text=text, vac_text=vac_text)
        except Exception as e:
            await bot.send_message(user_id, f"❌ Ошибка при проверке вакансии: {e}")
            return
        if text:
            await bot.send_message(user_id, text[:4096], parse_mode="HTML")
        else:
            await bot.send_message(user_id, "❌ Ошибка при проверке вакансии", parse_mode="HTML")
        os.remove(path)
    except Exception as e:
        await bot.send_message(user_id, f"❌ Ошибка в {path}: {e}")