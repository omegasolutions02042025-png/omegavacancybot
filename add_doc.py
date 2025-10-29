# -*- coding: utf-8 -*-
"""
Файл: build_pdf_from_source.py

Назначение:
1) Загрузить исходный файл (PDF/DOCX/HTML/TXT) в Gemini (google.generativeai).
2) Получить СТРОГО один самодостаточный HTML (переведённый на русский) без ```html-блоков.
3) Сконвертировать HTML в PDF через wkhtmltopdf.

Подготовка:
- pip install google-generativeai
- Установить wkhtmltopdf (и прописать путь ниже, если не в PATH).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv


load_dotenv()


# ========= НАСТРОЙКИ (ЗАПОЛНИ СВОИ) =========
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")   # можно оставить пустым и использовать переменную окружения
MODEL_NAME           = "gemini-2.5-pro"
TEMPERATURE          = 0.0                     # детерминированность
TOP_P                = 0.1
TOP_K                = 20
CANDIDATE_COUNT      = 1

# Полные пути к файлам/папкам
INPUT_FILE           = r"a.pdf"           # исходник: PDF/DOCX/HTML/TXT
OUTPUT_DIR           = r"out"                  # папка для результатов
OUTPUT_HTML_FILENAME = "result.html"                        # итоговый HTML
OUTPUT_PDF_FILENAME  = "result.pdf"                         # итоговый PDF

# Если wkhtmltopdf НЕ в PATH — укажи полный путь к исполняемому файлу:
WKHTMLTOPDF_PATH     = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"  # либо оставь "", если в PATH
# ============================================


PROMPT_TEMPLATE = """
ВЫВЕДИ СТРОГО ОДИН ПОЛНЫЙ HTML-ДОКУМЕНТ (<!doctype html> … </html>).
НЕ ДОБАВЛЯЙ НИКАКИХ КОДОВЫХ БЛОКОВ (```html, ```), ПРЕФИКСОВ, КОММЕНТАРИЕВ ИЛИ ТЕКСТА ВНЕ <html>.
НЕ ВСТАВЛЯЙ ЛИШНИЕ ПУСТЫЕ СТРОКИ, <br> ДЛЯ ОТСТУПОВ ИЛИ <p>&nbsp;</p>.

Ты — эксперт по разметке документов и верстке печатных макетов.
Задача: проанализировать ПРИКРЕПЛЕННЫЙ ФАЙЛ (PDF/DOCX/HTML/текст), ПЕРЕВЕСТИ ВСЁ СОДЕРЖИМОЕ НА РУССКИЙ ЯЗЫК,
сохранить структуру и вернуть самодостаточный HTML, готовый к печати (A4).

ТРЕБОВАНИЯ К ВЫВОДУ:
- Полноценный HTML с <head> и <body>. Никаких внешних CSS/JS.
- Встроенный CSS через <style> в <head>.
- Бумага A4 (portrait); поля ~18–20 мм (используй @page).
- Структура: H1/H2/H3, абзацы, списки, таблицы, подписи к изображениям, нумерация — всё сохраняем.
- Таблицы аккуратные, переносы строк, допустимы zebra-строки.
- Изображения из исходника — оставь <img> (если данных нет — НЕ вставляй заглушки).
- Переведи весь текст на русский, сохрани форматирование.
- Шрифты: "DejaVu Sans", Arial, sans-serif.
- Не используй множественные <br> подряд и пустые параграфы для отступов — отступы делай через CSS.

РЕКОМЕНДУЕМЫЙ БАЗОВЫЙ CSS (вставь в <style>):
  @page { size: A4; margin: 18mm; }
  html, body { height: 100%; }
  body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 12pt; line-height: 1.42; color: #111; }
  h1, h2, h3 { margin: 0 0 8pt; page-break-after: avoid; }
  p, li { orphans: 3; widows: 3; margin: 0 0 6pt; }
  ul, ol { margin: 0 0 8pt 18pt; padding: 0; }
  table { width: 100%; border-collapse: collapse; page-break-inside: auto; }
  th, td { border: 1px solid #ddd; padding: 6pt 8pt; vertical-align: top; }
  tr { page-break-inside: avoid; page-break-after: auto; }
  img { max-width: 100%; height: auto; display: block; page-break-inside: avoid; }
  .page-break { page-break-before: always; }

Верни ТОЛЬКО валидный HTML-документ, без префиксов ``` и без комментариев/объяснений вне HTML.
"""


def ensure_gemini() -> genai.GenerativeModel:
    """Конфигурируем SDK и возвращаем модель."""
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY не задан: впиши в константу или установи переменную окружения.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)


import time

# Таймауты/пуллинг для ожидания активации файла
FILE_POLL_SECONDS = 1.0   # шаг опроса
FILE_POLL_TIMEOUT = 60.0  # общий таймаут, сек

def _state_to_name(state_obj) -> str:
    """
    Унифицируем представление состояния в строку.
    Возможные варианты в SDK: "ACTIVE", enum с .name, или int (1/2/3).
    """
    # enum с .name
    name = getattr(state_obj, "name", None)
    if isinstance(name, str):
        return name.upper()

    # уже строка
    if isinstance(state_obj, str):
        return state_obj.upper()

    # иногда приходит int: 1=PROCESSING, 2=ACTIVE, 3=FAILED (по API)
    if isinstance(state_obj, int):
        return {1: "PROCESSING", 2: "ACTIVE", 3: "FAILED"}.get(state_obj, str(state_obj)).upper()

    # запасной вариант
    return str(state_obj).upper()

def upload_file(path: Path):
    """
    Загружаем файл и ждём, пока он станет ACTIVE.
    Совместимо с разными представлениями state.
    """
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    file_ref = genai.upload_file(path=str(path))

    # мгновенная проверка состояния
    state = _state_to_name(getattr(file_ref, "state", None))
    start_ts = time.time()

    # Если сразу ACTIVE — отлично
    if state == "ACTIVE":
        return file_ref

    # Если PROCESSING — ждём до таймаута
    while state == "PROCESSING" and (time.time() - start_ts) < FILE_POLL_TIMEOUT:
        time.sleep(FILE_POLL_SECONDS)
        # Обновляем состояние файла
        file_ref = genai.get_file(name=file_ref.name)
        state = _state_to_name(getattr(file_ref, "state", None))

    # Финальная развилка
    if state == "ACTIVE":
        return file_ref
    elif state == "FAILED":
        raise RuntimeError(f"Загрузка файла завершилась с ошибкой (state=FAILED). name={file_ref.name}")
    else:
        # например, вышли по таймауту или неизвестное состояние
        raise RuntimeError(f"Файл не активен: state={state}, name={file_ref.name}")


def call_model_to_html(model: genai.GenerativeModel, file_ref) -> str:
    """Запрашиваем у модели готовый HTML."""
    resp = model.generate_content(
        [file_ref, PROMPT_TEMPLATE],
        generation_config=genai.types.GenerationConfig(
            temperature=TEMPERATURE,
            top_p=TOP_P,
            top_k=TOP_K,
            candidate_count=CANDIDATE_COUNT,
        ),
    )
    html = (resp.text or "").strip()
    if not html or "<html" not in html.lower():
        raise RuntimeError("Модель не вернула валидный HTML-документ.")
    return html


def sanitize_html(raw: str) -> str:
    """Убираем ```html/``` и лишние пустые элементы, страхуем базовую структуру/print-фиксы."""
    html = raw.strip()

    # 1) Снять кодовые блоки ```html ... ``` и просто ```
    html = re.sub(r"^\s*```html\s*", "", html, flags=re.IGNORECASE)
    html = re.sub(r"\s*```\s*$", "", html)

    # 2) Убрать BOM/невидимые символы в начале
    html = html.lstrip("\ufeff\u200b\u2060")

    # 3) Схлопнуть последовательности <br> и пустых параграфов
    html = re.sub(r"(?i)(<br\s*/?>\s*){2,}", "<br>", html)
    html = re.sub(r"(?i)\s*<p>\s*(?:&nbsp;|\s)*</p>\s*", "", html)

    # 4) Если нет doctype — добавить
    if "<!doctype" not in html.lower():
        html = "<!doctype html>\n" + html

    # 5) Вставить/подменить печатные фиксы в <style>, если их не оказалось
    def inject_print_fixes(m):
        style_block = m.group(1)
        if "page-break-inside" not in style_block:
            style_block += """
/* print fixes */
table{page-break-inside:auto}
tr, td, th{page-break-inside:avoid; page-break-after:auto}
ul,ol{page-break-inside:avoid}
"""
        return f"<style>{style_block}</style>"

    html_with_style = re.sub(r"(?is)<style>(.*?)</style>", inject_print_fixes, html, count=1)
    if html_with_style:
        html = html_with_style

    return html


def write_text(path: Path, text: str):
    """Пишем текст в файл (UTF-8)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def find_wkhtmltopdf() -> str:
    """Находим wkhtmltopdf."""
    if WKHTMLTOPDF_PATH and Path(WKHTMLTOPDF_PATH).exists():
        return WKHTMLTOPDF_PATH
    exe = "wkhtmltopdf.exe" if os.name == "nt" else "wkhtmltopdf"
    found = shutil.which(exe)
    if not found:
        raise RuntimeError("wkhtmltopdf не найден. Установи и пропиши путь в WKHTMLTOPDF_PATH.")
    return found


def render_pdf(html_path: Path, pdf_path: Path):
    """Конвертируем HTML → PDF через wkhtmltopdf (стабильные флаги)."""
    wk = find_wkhtmltopdf()
    cmd = [
        wk,
        "--enable-local-file-access",
        "--print-media-type",
        "--dpi", "120",
        "--margin-top", "18mm",
        "--margin-bottom", "18mm",
        "--margin-left", "18mm",
        "--margin-right", "18mm",
        # Если будут «дыры», можно поэкспериментировать:
        # "--disable-smart-shrinking",
        # "--viewport-size", "1280x1800",
        str(html_path),
        str(pdf_path),
    ]
    subprocess.run(cmd, check=True)


def run():
    inp = Path(INPUT_FILE)
    out_dir = Path(OUTPUT_DIR)
    html_out = out_dir / OUTPUT_HTML_FILENAME
    pdf_out = out_dir / OUTPUT_PDF_FILENAME

    print(f"[INFO] Исходный файл: {inp}")
    print(f"[INFO] Модель: {MODEL_NAME}")

    model = ensure_gemini()
    file_ref = upload_file(inp)

    html = call_model_to_html(model, file_ref)
    html = sanitize_html(html)

    # Быстрые проверки
    if not html.lower().lstrip().startswith("<!doctype html"):
        raise RuntimeError("HTML не начинается с <!doctype html> — модель прислала лишний префикс.")
    if "<html" not in html.lower():
        raise RuntimeError("В ответе нет <html> — невалидная разметка.")

    write_text(html_out, html)
    print(f"[OK] HTML сохранён: {html_out}")

    render_pdf(html_out, pdf_out)
    print(f"[OK] PDF готов: {pdf_out}")


if __name__ == "__main__":
    run()
