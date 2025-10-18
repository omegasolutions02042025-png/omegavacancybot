from PIL import Image, ImageEnhance, ImageFilter
import pytesseract, re

# Укажи путь к tesseract, если не в PATH
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

RUS_TRIGGER = ("Код для входа", "Код для входа в Telegram", "Код для входа в Телеграм")

def _preprocess(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.resize((img.width * 2, img.height * 2))
    # мягкая бинаризация: оставляем возможность распознать двоеточие/буквы в первом проходе
    return img

def _cleanup_ocr_text(s: str) -> str:
    # Частые подмены: латиница/кириллица и цифры
    table = str.maketrans({
        "O":"0","o":"0","І":"1","l":"1","I":"1","Б":"6","б":"6","З":"3","з":"3",
        "S":"5","§":"5"
    })
    return s.translate(table)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_code_from_image(file_or_path):
    """Извлекает 5-значный Telegram-код даже при OCR-ошибках."""
    try:
        file_or_path.seek(0)
    except AttributeError:
        pass

    img = Image.open(file_or_path)
    img = img.convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(2.8)
    img = img.resize((img.width * 2, img.height * 2))

    text = pytesseract.image_to_string(img, lang="rus+eng", config="--psm 6")
    print("🧩 Распознанный текст:\n", text)

    # Ищем строго 5 цифр после фразы: "Код для входа в Telegram:" (с учётом возможных пробелов/типов двоеточий)
    pattern_strict = r"Код\s+для\s+входа\s+в\s+Telegram\s*[:\-–—]?\s*([0-9]{5})"
    m = re.search(pattern_strict, text, flags=re.IGNORECASE)
    if m:
        code = m.group(1)
        print(f"✅ Найден код по фразе: {code}")
        return code
    if not m:
        code = text.split(":")[1].split(".")[0].strip()
        print(f"✅ Найден код по фразе: {code}")
        return code
    
    print("❌ Код не найден по фразе 'Код для входа в Telegram:'.")
    return None

