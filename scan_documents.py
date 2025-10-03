from docx import Document
from PyPDF2 import PdfReader
import pypandoc
from aiogram import Bot

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

async def process_file(path: str, bot: Bot, user_id: int|str):
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
            print(f"⚠️ Формат {ext} не поддерживается: {path}")
            return
        print(f"✅ {path} обработан → {len(text)} символов")
        await bot.send_message(user_id, text)
    except Exception as e:
        print(f"❌ Ошибка в {path}: {e}")