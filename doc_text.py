import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from striprtf.striprtf import rtf_to_text


ANTIWORD_PATH = r"C:\antiword\antiword.exe"      # твой путь
ANTIWORD_HOME = r"C:\antiword"                   # папка с UTF-8.TXT
# маппинг не используем — он ломает форматирование RTF-файлов, нам он не нужен.


def is_rtf_file(path: str) -> bool:
    """Проверяем, что файл .doc — на самом деле RTF."""
    try:
        with open(path, "rb") as f:
            head = f.read(5)
        return head.startswith(b"{\\rtf")
    except:
        return False


def extract_rtf(path: str) -> str:
    """Читает RTF-файл и возвращает текст."""
    try:
        with open(path, "r", encoding="cp1251", errors="ignore") as f:
            data = f.read()
    except:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()

    text = rtf_to_text(data)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_doc_via_antiword(path: str) -> str:
    """Вызывает antiword для настоящих DOC-файлов."""
    if not Path(ANTIWORD_PATH).exists():
        raise RuntimeError("antiword.exe не найден, проверь путь.")

    env = os.environ.copy()
    env.setdefault("HOME", ANTIWORD_HOME)
    env.setdefault("ANTIWORDHOME", ANTIWORD_HOME)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_doc = Path(tmpdir) / "file.doc"
        shutil.copy(path, tmp_doc)

        result = subprocess.run(
            [ANTIWORD_PATH, "-w", "0", str(tmp_doc)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

    if result.returncode != 0:
        stdout = result.stdout.decode("cp1251", errors="ignore")
        stderr = result.stderr.decode("cp1251", errors="ignore")
        raise RuntimeError(f"Ошибка antiword:\n{stdout}\n{stderr}")

    text = result.stdout.decode("cp1251", errors="ignore")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def process_docc(path: str) -> str:
    """Универсальная обработка .doc/.rtf/.doc(RTF)."""

    path = os.path.abspath(path)
    print(f"📄 Обработка файла: {path}")

    # 1. RTF disguised as DOC
    if is_rtf_file(path):
        print("⚠️ Определено: файл — RTF, маскирующийся под .doc. Использую striprtf.")
        return extract_rtf(path)

    print("ℹ️ Файл выглядит как настоящий DOC — запускаю antiword...")
    return extract_doc_via_antiword(path)