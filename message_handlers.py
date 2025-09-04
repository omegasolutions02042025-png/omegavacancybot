import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import re
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User
from db import add_message_mapping
from gpt import process_vacancy
from googlesheets import find_rate_in_sheet_gspread
from funcs import is_russia_only_citizenship, oplata_filter, check_project_duration
from telethon.errors import FloodWaitError
from bot_utils import send_error_to_admin, update_activity
import os

GROUP_ID = os.getenv('GROUP_ID')

def has_strikethrough(message):
    """Проверяет наличие зачёркнутого текста в сообщении"""
    if not message.entities:
        return False
    for entity in message.entities:
        if entity.__class__.__name__ == 'MessageEntityStrike':
            return True
    return False

async def register_handler(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal):
    """Регистрирует обработчик новых сообщений из каналов"""
    @telethon_client.on(events.NewMessage(chats=CHANNELS))
    async def new_channel_message_handler(event):
        update_activity()
        
        text_orig = event.message.message or ""
        if not text_orig:
            return

        if is_russia_only_citizenship(text_orig):
            return

        # Проверка зачёркнутого текста
        if has_strikethrough(event.message):
            return
            
        if oplata_filter(text_orig):
            return
            
        if check_project_duration(text_orig):
            return
            
        entity = await telethon_client.get_entity(int(GROUP_ID))
        
        try:
            text_gpt = await process_vacancy(text_orig)
        except Exception as e:
            # Отправляем ошибку в чат вместо print
            from main import bot
            await send_error_to_admin(bot, str(e), "process_vacancy")
            return
            
        if text_gpt == None:
            return
        else:
            try:
                text = text_gpt.get("text")
                if text == None:
                   return
                   
                vac_id = text_gpt.get('vacancy_id')
                rate = text_gpt.get("rate")
                vacancy = text_gpt.get('vacancy_title')
                
                deadline_date = text_gpt.get("deadline_date")
                deadline_time = text_gpt.get("deadline_time")

                if rate == None:
                    text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"

                elif int(rate) == 0:
                   text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                else:
                    rate = int(rate)
                    rate = round(rate /5) * 5
                    if rate == None:
                        return
                    else:
                        rate = find_rate_in_sheet_gspread(rate)
                        rate = re.sub(r'\s+', '', rate)
                        rounded = math.ceil(int(rate) / 100) * 100  

                        rate = f"{rounded:,}".replace(",", " ")

                    if rate is None or vacancy is None:
                        return
                    else:
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"

            except Exception as e:
                from main import bot
                await send_error_to_admin(bot, str(e), "message_processing")
                return
                
        try:
            forwarded_msg = await telethon_client.send_message(entity=entity, message=text_cleaned, parse_mode='html')
        except Exception:
            forwarded_msg = await telethon_client.send_message(entity=entity, message=text_cleaned)

        # Сохраняем сопоставление
        async with AsyncSessionLocal() as session:
            await add_message_mapping(
                session,
                src_chat_id=event.chat_id,
                src_msg_id=event.message.id,
                dst_chat_id=int(GROUP_ID),
                dst_msg_id=forwarded_msg.id,
                deadline_date=deadline_date,
                deadline_time=deadline_time
            )

    return new_channel_message_handler

async def register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal):
    """Регистрирует обработчик сообщений из топиков"""
    
    # Берём все уникальные чаты из TOPIC_MAP для подписки
    chats_to_watch = list({chat_id for chat_id, _ in TOPIC_MAP.keys()})

    @telethon_client.on(events.NewMessage(chats=chats_to_watch))
    async def new_topic_message(event):
        update_activity()
        
        # Проверяем, что сообщение из топика
        if not hasattr(event.message, 'reply_to') or not event.message.reply_to:
            return  # Не топик-сообщение
        
        src_topic_id = event.message.reply_to.reply_to_msg_id
        
        # Ищем точное соответствие чата и топика
        key = (event.chat_id, src_topic_id)
        if key not in TOPIC_MAP:
            return  # Этот топик не отслеживаем

        dst_chat_id, dst_topic_id = TOPIC_MAP[key]

        text = getattr(event.message, 'message', '') or ""
        if not text:
            return

        # Добавляем все необходимые фильтры
        if is_russia_only_citizenship(text):
            return

        if has_strikethrough(event.message):
            return

        if oplata_filter(text):
            return

        if check_project_duration(text):
            return

        try:
            text_gpt = await process_vacancy(text)
        except Exception as e:
            from main import bot
            await send_error_to_admin(bot, str(e), "process_vacancy_topic")
            return

        if text_gpt is None or text_gpt == 'None':
            return

        try:
            text = text_gpt.get("text")
            if text == None or text == 'None':
                return
            vac_id = text_gpt.get('vacancy_id')
            rate = text_gpt.get("rate")
            vacancy = text_gpt.get('vacancy_title')
            if vacancy is None or vacancy == 'None':
                return
            if vac_id is None or vac_id == 'None':
                return

            deadline_date = text_gpt.get("deadline_date")
            deadline_time = text_gpt.get("deadline_time")
            utochnenie = text_gpt.get("utochnenie")
            
            # Исправляем логику обработки ставки
            if rate is None or rate == 'None' or int(rate) == 0:
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
            else:
                rate = int(rate)
                rate = round(rate / 5) * 5
                rate = find_rate_in_sheet_gspread(rate)
                if rate is None or vacancy is None:
                    return
                rate = re.sub(r'\s+', '', rate)
                rounded = math.ceil(int(rate) / 100) * 100
                rate = f"{rounded:,}".replace(",", " ")
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"

        except Exception as e:
            from main import bot
            await send_error_to_admin(bot, str(e), "topic_message_processing")
            return

        try:
            if utochnenie == 'True' or utochnenie is True:
                await telethon_client.send_message(
                    GROUP_ID,
                    message=text_cleaned,
                )
                return  # Если отправили в группу уточнений, не отправляем в канал
        except Exception as e:
            from main import bot
            await send_error_to_admin(bot, str(e), "send_to_clarification_group")
            return

        try:
            forwarded_msg = await telethon_client.send_message(
                dst_chat_id,
                message=text_cleaned,
                parse_mode='html',
                reply_to=dst_topic_id
            )
        except Exception as e:
            from main import bot
            await send_error_to_admin(bot, str(e), "send_to_channel")
            return

        # Сохраняем сопоставление сообщений
        async with AsyncSessionLocal() as session:
            await add_message_mapping(
                session,
                src_chat_id=event.chat_id,
                src_msg_id=event.message.id,
                dst_chat_id=dst_chat_id,
                dst_msg_id=forwarded_msg.id,
                deadline_date=deadline_date,
                deadline_time=deadline_time
            )
