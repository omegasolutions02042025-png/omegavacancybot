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
