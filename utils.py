import asyncio, random, time
from collections import deque
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramNetworkError
from telethon import TelegramClient
from aiogram import Bot
# Ограничение: не более N сообщений за WINDOW сек на чат
MAX_MSG = 18
WINDOW = 60.0
_CHAT_BUCKETS: dict[tuple[int, int|None], deque[float]] = {}

async def throttle_chat(chat_id: int, thread_id: int | None):
    key = (chat_id, thread_id)
    now = time.monotonic()
    bucket = _CHAT_BUCKETS.setdefault(key, deque())
    while bucket and (now - bucket[0]) > WINDOW:
        bucket.popleft()
    if len(bucket) >= MAX_MSG:
        sleep_for = WINDOW - (now - bucket[0]) + 0.05
        await asyncio.sleep(sleep_for)
        return await throttle_chat(chat_id, thread_id)
    bucket.append(now)

async def safe_send_message(bot, chat_id: int, text: str, *, message_thread_id: int | None = None, **kw):
    """Отправка с обработкой FloodWait/сетевых ошибок + троттлингом."""
    await throttle_chat(chat_id, message_thread_id)
    attempt = 0
    while True:
        try:
            return await bot.send_message(chat_id=chat_id, text=text, message_thread_id=message_thread_id, **kw)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramNetworkError:
            attempt += 1
            await asyncio.sleep(min(2 ** attempt, 10) + random.random())
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return None
            raise

import re

_TELEGRAM_PATTERNS = [
    # @username (5-32 символов: латиница, цифры, подчёркивание)
    re.compile(r'(?<!\w)@([A-Za-z0-9_]{5,32})(?!\w)'),
    # https://t.me/username  или http://telegram.me/username  (+ возможные параметры)
    re.compile(r'(?i)\bhttps?://(?:t\.me|telegram\.me)/([A-Za-z0-9_]{5,32})(?:\b|/|\?|#)'),
    # tg://resolve?domain=username
    re.compile(r'(?i)\btg://resolve\?[^ \t\r\n]*\bdomain=([A-Za-z0-9_]{5,32})\b'),
]

def extract_telegram_usernames(text: str) -> list[str]:
    """
    Извлекает Telegram-юзернеймы из текста.
    Возвращает список уникальных имён БЕЗ '@' в порядке первого появления.
    """
    if not text:
        return []

    found = []
    seen = set()

    for pattern in _TELEGRAM_PATTERNS:
        for m in pattern.findall(text):
            username = m if isinstance(m, str) else m[0]
            if username == 'omega_vacancy_bot':
                continue
            # нормализация: Telegram имена без регистра-значимости
            key = username.lower()
            if key not in seen:
                seen.add(key)
                found.append(username)

    return '@' + found[0]



from typing import Iterable, Mapping

def to_csv(data: Mapping | Iterable | None, canon_map: dict[str, str] | None = None, sep: str = ", ") -> str:
    """
    Превращает dict/iterable в CSV без пустых значений и дублей.
    Если передать canon_map (ключи в нижнем регистре) — мапит на канон.
    """
    if not data:
        return ""
    # берём элементы
    if isinstance(data, Mapping):
        items = [k for k, v in data.items() if v]  # только True-флаги
    else:
        items = list(data)

    out, seen = [], set()
    for k in items:
        if k is None:
            continue
        s = str(k).strip().strip(",")
        if not s:
            continue
        key_lc = s.lower()
        # канонизация имён при необходимости
        if canon_map:
            s = canon_map.get(key_lc, s)
            key_lc = s.lower()
        if key_lc in seen:
            continue
        seen.add(key_lc)
        out.append(s)
    return sep.join(out)



def pick_flags(d) -> list[str]:
    """Берём только ключи со значением True, без пустых/пробельных."""
    d = d or {}
    return [str(k).strip() for k, v in d.items() if v and str(k).strip()]



MAX_TG = 4096

async def send_long_message(bot: Bot, chat_id: int | str, text: str, tread_id: int | None = None, **kwargs):
    """
    Отправляет сообщение(я) в Telegram, если text > 4096 — режет на части.
    kwargs уйдут в bot.send_message (parse_mode, reply_markup и т.п.)
    """
    if not text:
        return

    # режем по 4096
    parts = [text[i:i+MAX_TG] for i in range(0, len(text), MAX_TG)]

    for part in parts:
        if tread_id:
            await bot.send_message(chat_id=chat_id, text=part, message_thread_id=tread_id, parse_mode='HTML')
        else:
            await bot.send_message(chat_id=chat_id, text=part, parse_mode = 'HTML')


import re
import aiohttp
from pathlib import Path

async def download_gdrive_files(urls: list[str], user_id: int, tread_id: int):
    dest_dir = f"downloads/{user_id}_{tread_id}"
    dest_path = Path(dest_dir)
    if not dest_path.exists():
        dest_path.mkdir(parents=True, exist_ok=True)

    def extract_id(url: str) -> str | None:
        m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
        return m.group(1) if m else None

    def sanitize_name(name: str) -> str:
        # на всякий случай убираем запрещённые для Windows символы
        bad = '<>:"/\\|?*'
        for ch in bad:
            name = name.replace(ch, "_")
        name = name.strip()
        return name or "file.bin"

    async def save_resp(resp, out_path: Path):
        # ВАЖНО: создать родительские папки
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as f:
            async for chunk in resp.content.iter_chunked(1 << 15):
                f.write(chunk)

    base = "https://drive.google.com/uc?export=download"

    async with aiohttp.ClientSession() as session:
        for url in urls:
            file_id = extract_id(url)
            if not file_id:
                print(f"⚠️ пропускаю: {url}")
                continue

            r1 = await session.get(base, params={"id": file_id}, allow_redirects=True)
            if r1.status != 200:
                print(f"❌ {url} -> HTTP {r1.status}")
                continue

            # имя по умолчанию
            filename = f"{file_id}.bin"

            cd = r1.headers.get("Content-Disposition", "")
            mname = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.I)
            if mname:
                filename = sanitize_name(mname.group(1))
            else:
                filename = sanitize_name(filename)

            out_path = dest_path / filename

            # если сразу файл — сохраняем
            if "Content-Disposition" in r1.headers:
                await save_resp(r1, out_path)
                print(f"✅ скачал: {out_path}")
                continue

            # иначе confirm
            text = await r1.text()
            token = None
            for k, v in r1.cookies.items():
                if k.startswith("download_warning"):
                    token = v.value
                    break
            if not token:
                m = re.search(r"confirm=([0-9A-Za-z_]+)&", text)
                if m:
                    token = m.group(1)

            params = {"id": file_id}
            if token:
                params["confirm"] = token

            r2 = await session.get(base, params=params, allow_redirects=True)
            if r2.status != 200:
                print(f"❌ {url} -> HTTP {r2.status} на confirm")
                continue

            cd2 = r2.headers.get("Content-Disposition", "")
            mname2 = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd2, flags=re.I)
            if mname2:
                out_path = dest_path / sanitize_name(mname2.group(1))

            await save_resp(r2, out_path)
            print(f"✅ скачал: {out_path}")



import re

def replace_channel_mail(text: str) -> str | None:
    # Паттерн 1: для поиска старого блока (ID вакансии может меняться)

    
    # Паттерн 2: для замены "Контакт для вопросов: @username"
    pattern2 = re.compile(
        r'Контакт(?:ы)?\s+для\s+вопросов:\s*@[A-Za-z0-9_]{3,32}',
        re.MULTILINE | re.IGNORECASE
    )

    # Новый блок для замены
    new_block = """Требования к резюме:

1️⃣ Полное ФИО и дата рождения
2️⃣ Локация
3️⃣ Срок выхода на проект
4️⃣ Формат оформления: ИП/самозанятость/штат
5️⃣ Минимальная зарплатная ставка
6️⃣ Контакты: телефон, Telegram, e-mail
7️⃣ Описание проектов:
— название
— роль в команде
— стек технологий
— описание задач и результатов

📩 Отправляйте резюме с указанием ID вакансии (например, «00058554 Ruby on Rails») и всей информации из запроса на e-mail: cv@omega-solutions.ru  или в личку @DmitriyOmega."""

    # Пробуем заменить "Контакт для вопросов" (паттерн 2)
    new_text = pattern2.sub(new_block, text)
    
    # Убираем множественные пробелы подряд (заменяем на один пробел)
    new_text = re.sub(r' {2,}', ' ', new_text)
    
    # Убираем множественные переводы строк подряд (больше 2 подряд заменяем на 2)
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)
    if new_text == text:
        return None
    
    return new_text

