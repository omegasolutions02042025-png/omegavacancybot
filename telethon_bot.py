import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import re
import random
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User
from db import get_all_channels, add_message_mapping, remove_message_mapping, get_all_message_mappings, get_next_sequence_number
from gpt import del_contacts_gpt
from googlesheets import find_rate_in_sheet_gspread
from typing import Tuple, Optional

# --- Telethon функции ---

async def forward_recent_posts(telethon_client, CHANNELS, GROUP_ID):
    # aware-дата в UTC
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)

    entity = await telethon_client.get_entity(int(GROUP_ID))

    for source in CHANNELS:
        async for message in telethon_client.iter_messages(source):
            # Если сообщение старше 2 недель — прекращаем итерацию
            if message.date < cutoff_date:
                break

            try:
                text_orig = message.message or ""
                if not text_orig:
                    continue
                
                text = remove_request_id(text_orig)
                if not text:
                    continue

                if has_strikethrough(message):
                    print(f"❌ Сообщение {message.id} в канале {entity} содержит зачёркнутый текст — пропускаем")
                    continue
                
                try:
                    text_gpt = await del_contacts_gpt(text)
                except Exception as e:
                    print(e)
                    continue
                if text_gpt == None:
                    continue
                else:
                    try:
                        bd_id = await generate_bd_id()
                        text_gpt = json.loads(text_gpt)
                        text = text_gpt.get("text")
                        rate = text_gpt.get("rate")
                        if rate == None:
                            text_cleaned = f"🆔{bd_id}\nМесячная ставка(на руки) до: {rate} RUB\n{text}"
                        if rate == 0:
                            text_cleaned = f"🆔{bd_id}\nМесячная ставка(на руки) до: {rate} RUB\n{text}"
                        else:
                            rate = int(rate)
                            rate = round(rate /5) * 5
                            print(rate)
                            if rate == None:
                                continue
                            else:
                                rate = find_rate_in_sheet_gspread(rate)
                                rate = re.sub(r'\s+', '', rate)
                                rounded = math.ceil(int(rate) / 100) * 100  

                                rate = f"{rounded:,}".replace(",", " ")
                                print(rate)

                                if rate == None:
                                    continue
                                else:
                                    
                                    text_cleaned = f"🆔{bd_id}\nМесячная ставка(на руки) до: {rate} RUB\n{text}"
                                
                    except Exception as e:
                        print(e)
                        continue

                await telethon_client.send_message(entity, text_cleaned)
                print(f"Переслал из {source}: {message.id}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Ошибка при пересылке из {source}: {e}")



async def forward_messages_from_topics(telethon_client, TOPIC_MAP, days=1):
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    print(f"[i] Берем сообщения с {cutoff_date}")

    for (src_chat, src_topic_id), (dst_chat, dst_topic_id) in TOPIC_MAP.items():
        print(f"[i] Проверяем топик {src_topic_id} в чате {src_chat}")
        try:
            async for msg in telethon_client.iter_messages(
                src_chat,
                reply_to=src_topic_id,   # <-- вот тут обязательно thread_id
                reverse=False,            # чтобы идти от новых к старым
            ):
                if msg.date < cutoff_date:
                    print(msg.date)
                    await asyncio.sleep(5)
                    break  # старые сообщения не нужны
                text = msg.text
                #text , vac_id = remove_request_id(text=text)
                if not text:
                    continue

                if has_strikethrough(msg):
                    print(f"❌ Сообщение {msg.id} содержит зачёркнутый текст — пропускаем")
                    continue
                try:
                    text_gpt = await del_contacts_gpt(text)
                    #print(text)
                except Exception as e:
                    print(e)
                    continue
                if text_gpt == None:
                    continue
                else:
                    try:
                        
                        
                        #text_gpt = json.loads(text_gpt)
                        text = text_gpt.get("text")
                        
                        vac_id = text_gpt.get('vacancy_id')
                        rate = text_gpt.get("rate")
                        vacancy = text_gpt.get('vacancy_title')
                        
                        deadline_date = text_gpt.get("deadline_date")  # "DD.MM.YYYY"
                        deadline_time = text_gpt.get("deadline_time") 
                        
                         

                        if rate == None:
                            
                            text_cleaned = f"{vacancy}\n\n🆔{vac_id}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"
                            

                        if rate == 0:
                           text_cleaned = f"{vacancy}\n\n🆔{vac_id}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"
                        else:
                            rate = int(rate)
                            rate = round(rate /5) * 5
                            print(rate)
                            if rate == None:
                                continue
                            else:
                                rate = find_rate_in_sheet_gspread(rate)
                                rate = re.sub(r'\s+', '', rate)
                                rounded = math.ceil(int(rate) / 100) * 100  

                                rate = f"{rounded:,}".replace(",", " ")
                                print(rate)

                            if rate == None:
                                continue
                            else:
                                    
                                text_cleaned = f"{vacancy}\n\n🆔{vac_id}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"
                                
                    except Exception as e:
                        print(e)
                        continue
                    try:
                        await telethon_client.send_message(
                                    dst_chat,
                                    text_cleaned,
                                    file=msg.media,
                                    reply_to=dst_topic_id
                                )
                        
                    except Exception as e:
                        print('Ошибка при пересылке', e)
                        continue
                    await asyncio.sleep(0.5)
            
                await asyncio.sleep(random.uniform(2, 5))  # небольшой таймаут между отправками
        except Exception as e:
            print(f"[!] Ошибка при чтении топика {src_topic_id} в чате {src_chat}: {e}")

def has_strikethrough(message):
    if not message.entities:
        return False
    for entity in message.entities:
        if entity.__class__.__name__ == 'MessageEntityStrike':
            return True
    return False

async def register_handler(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal):
    @telethon_client.on(events.NewMessage(chats=CHANNELS))
    async def new_channel_message_handler(event):
        text_orig = event.message.message or ""
        if not text_orig:
            return

        text = remove_request_id(text_orig)
        if not text:
            return

        # Проверка зачёркнутого текста
        if has_strikethrough(event.message):
            print(f"❌ Сообщение {event.message.id} в канале {event.chat_id} содержит зачёркнутый текст — пропускаем")
            return

        entity = await telethon_client.get_entity(int(GROUP_ID))
        
        try:
            text_gpt = await del_contacts_gpt(text)
        except Exception as e:
            print(e)
            return
        if text_gpt == None:
            return
        else:
            try:
                bd_id = await generate_bd_id()
                
                text = text_gpt.get("text")
                rate = text_gpt.get("rate")
                vac_id = text_gpt.get('vacancy_id')
                deadline_date = text_gpt.get("deadline_date")  # "DD.MM.YYYY"
                deadline_time = text_gpt.get("deadline_time") 
                if rate == None:
                    text = f"🆔{bd_id+vac_id}\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n{text}"

                if rate == 0:
                    text = f"🆔{bd_id}\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n{text}"
                else:
                    rate = int(rate)
                    rate = round(rate /5) * 5
                    print(rate)
                    if rate == None:
                        return
                    
                    else:
                        rate = find_rate_in_sheet_gspread(rate)
                        rate = re.sub(r'\s+', '', rate)
                        rounded = math.ceil(int(rate) / 100) * 100  

                        rate = f"{rounded:,}".replace(",", " ")
                        print(rate)

                        if rate == None:
                            return
                        
                        else:
                                    
                            text = f"🆔{bd_id}\nМесячная ставка(на руки) до: {rate} RUB\n{text}"

            except Exception as e:
                print(e)
                return
        try:
            forwarded_msg = await telethon_client.send_message(entity=entity, message=text, parse_mode='html')
        except Exception:
            forwarded_msg = await telethon_client.send_message(entity=entity, message=text)

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

        print("❌ Ни одно обязательное слово не найдено")

    return new_channel_message_handler

async def list_all_dialogs(telethon_client, PHONE_NUMBER):
    await telethon_client.start(phone=PHONE_NUMBER)

    async for dialog in telethon_client.iter_dialogs():
        entity = dialog.entity

        if isinstance(entity, Channel):
            kind = 'Канал'
        elif isinstance(entity, Chat):
            kind = 'Группа'
        elif isinstance(entity, User):
            kind = 'Пользователь'
        else:
            kind = 'Другое'

        print(f"{kind}: {dialog.name} — ID: {entity.id}")

from datetime import datetime, timezone

async def monitor_and_cleanup(telethon_client, AsyncSessionLocal):
    while True:
        async with AsyncSessionLocal() as session:
            mappings = await get_all_message_mappings(session)

            to_delete = []
            for mapping in mappings:
                try:
                    msg = await telethon_client.get_messages(mapping.src_chat_id, ids=mapping.src_msg_id)
                    
                    # Если сообщение удалено или есть зачеркивание
                    if msg is None or has_strikethrough(msg):
                        print(f"Удаляем пересланное сообщение {mapping.dst_msg_id} из {mapping.dst_chat_id}")
                        await telethon_client.delete_messages(mapping.dst_chat_id, message_ids=mapping.dst_msg_id)
                        to_delete.append(mapping)
                        continue

                    # Проверка на слово "стоп"
                    if msg.message and "стоп" in msg.message.lower():
                        print(f"Удаляем по слову 'стоп' сообщение {mapping.dst_msg_id} из {mapping.dst_chat_id}")
                        await telethon_client.delete_messages(mapping.dst_chat_id, message_ids=mapping.dst_msg_id)
                        to_delete.append(mapping)
                        continue

                    # Проверка дедлайна
                    if mapping.deadline_date:
                        # Формируем datetime объекта дедлайна
                        if mapping.deadline_time:
                            deadline_dt = datetime.strptime(f"{mapping.deadline_date} {mapping.deadline_time}", "%d.%m.%Y %H:%M")
                        else:
                            # Если время не указано, ставим конец дня
                            deadline_dt = datetime.strptime(mapping.deadline_date, "%d.%m.%Y").replace(hour=23, minute=59)

                        # Сравниваем с текущим временем UTC
                        now_utc = datetime.now(timezone.utc)
                        if deadline_dt.replace(tzinfo=timezone.utc) <= now_utc:
                            print(f"Удаляем сообщение по дедлайну {mapping.dst_msg_id} из {mapping.dst_chat_id}")
                            await telethon_client.delete_messages(mapping.dst_chat_id, message_ids=mapping.dst_msg_id)
                            to_delete.append(mapping)
                            continue

                except Exception as e:
                    print(f"Ошибка проверки сообщения {mapping.src_msg_id} в {mapping.src_chat_id}: {e}")

            # Удаляем записи из БД
            for mapping in to_delete:
                await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)

        await asyncio.sleep(60)  # проверяем каждую минуту
  # проверяем каждую минуту


async def generate_bd_id() -> str:
    sequence_num = await get_next_sequence_number()
    seq_str = str(sequence_num).zfill(4)
    return f"{seq_str}"

def remove_request_id(text: str) -> Tuple[str, Optional[str]]:
    """
    Удаляет из текста идентификатор вакансии вида:
    🆔 XX-1234 или 🆔 1234
    Возвращает:
        - очищенный текст
        - 4-значный ID как строку (или None, если не найден)
    """
    match = re.search(r'🆔(?:[A-Z]{2}-)?(\d{4})', text)
    vacancy_id = match.group(1) if match else None
    cleaned_text = re.sub(r'🆔(?:[A-Z]{2}-)?\d{4}', '', text).strip()
    return cleaned_text, vacancy_id


async def register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal):
    @telethon_client.on(events.NewMessage(chats=list({chat_id for chat_id, _ in TOPIC_MAP.keys()})))
    async def new_topic_message(event):
        key = (event.chat_id, getattr(event.message, 'message_thread_id', 0))
        if key not in TOPIC_MAP:
            return  # этот топик не отслеживаем

        dst_chat_id, dst_topic_id = TOPIC_MAP[key]

        text_orig = event.message.message or ""
        if not text_orig:
            return

        text = remove_request_id(text_orig)
        if not text:
            return

        if has_strikethrough(event.message):
            print(f"❌ Сообщение {event.message.id} в канале {event.chat_id} содержит зачёркнутый текст — пропускаем")
            return

        try:
            text_gpt = await del_contacts_gpt(text)
        except Exception as e:
            print(e)
            return
        if text_gpt is None:
            return

        try:
            bd_id = await generate_bd_id()
            text_gpt = json.loads(text_gpt)
            text = text_gpt.get("text")
            rate = text_gpt.get("rate")
            deadline_date = text_gpt.get("deadline_date")
            deadline_time = text_gpt.get("deadline_time")

            if rate in (None, 0):
                text = f"🆔{bd_id}\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n{text}"
            else:
                rate = int(rate)
                rate = round(rate / 5) * 5
                rate = find_rate_in_sheet_gspread(rate)
                rate = re.sub(r'\s+', '', rate)
                rounded = math.ceil(int(rate) / 100) * 100
                rate = f"{rounded:,}".replace(",", " ")
                text = f"🆔{bd_id}\nМесячная ставка(на руки) до: {rate} RUB\n{text}"

        except Exception as e:
            print(e)
            return

        try:
            forwarded_msg = await telethon_client.send_message(
                dst_chat_id,
                message=text,
                parse_mode='html'
            )
        except Exception:
            forwarded_msg = await telethon_client.send_message(
                dst_chat_id,
                message=text
            )

        # Сохраняем сопоставление
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

    