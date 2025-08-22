
import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import re
import random
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User
from db import get_all_channels, add_message_mapping, remove_message_mapping, get_all_message_mappings, get_next_sequence_number
from gpt import del_contacts_gpt, process_vacancy
from googlesheets import find_rate_in_sheet_gspread
from typing import Tuple, Optional
from funcs import is_russia_only_citizenship, oplata_filter, check_project_duration
from telethon.errors import FloodWaitError

import teleton_client
import os

VACANCY_ID_REGEX = re.compile(r"🆔\s*([A-Z]{2}-\d+|\d+)", re.UNICODE)
GROUP_ID = os.getenv('GROUP_ID')

#
#
# --- Telethon функции ---

async def forward_recent_posts(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal):
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
                
                if is_russia_only_citizenship(text):
                    print('Гражданство не подходит')
                    continue

                if has_strikethrough(message):
                    print(f"❌ Сообщение {message.id} в канале {entity} содержит зачёркнутый текст — пропускаем")
                    continue
                if oplata_filter(text):
                    print('Оплата не подходит')
                    continue
                if check_project_duration(text):
                    print('Маленькая продолжительность проекта')
                    asyncio.sleep(3)
                    continue
                try:
                    text_gpt = await process_vacancy(text)
                    #print(text)
                except Exception as e:
                    print(e)
                    continue
                if text_gpt == None:
                    continue
                else:


                    try:
                        text = text_gpt.get("text")
                        if text == None:
                           print('Вакансия отсеяна')
                           continue            
                        vac_id = text_gpt.get('vacancy_id')
                        print(vac_id)
                        rate = text_gpt.get("rate")
                        vacancy = text_gpt.get('vacancy_title')
                        if vacancy is None:
                            continue
                                    
                        deadline_date = text_gpt.get("deadline_date")  # "DD.MM.YYYY"
                        deadline_time = text_gpt.get("deadline_time") 
                                    
                                    

                        if rate == None:
                                        
                            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                                        

                        if int(rate) == 0:
                            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
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

                                if rate is None or vacancy is None:
                                    return
                                else:
                                                
                                    text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"
                                    
                    except Exception as e:
                            print(e)
                            continue

                forwarded_msg = await telethon_client.send_message(entity, text_cleaned)
                print(f"Переслал из {source}: {message.id}")
                async with AsyncSessionLocal() as session:
                    await add_message_mapping(
                        session,
                        src_chat_id=source,
                        src_msg_id=message.id,
                        dst_chat_id=entity,
                        dst_msg_id=forwarded_msg.id,
                        deadline_date=deadline_date,
                        deadline_time=deadline_time
                    )
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Ошибка при пересылке из {source}: {e}")



async def forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=14):
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    print(f"[i] Берем сообщения с {cutoff_date}")

    for (src_chat, src_topic_id), (dst_chat, dst_topic_id) in TOPIC_MAP.items():
        print(f"[i] Проверяем топик {src_topic_id} в чате {src_chat}")
        try:
            async for msg in telethon_client.iter_messages(
                src_chat,
                reply_to=src_topic_id,
                reverse=False,
            ):
                if msg.date < cutoff_date:
                    print(msg.date)
                    await asyncio.sleep(5)
                    break
                
                text = msg.text
                if not text:
                    continue
                if is_russia_only_citizenship(text):
                    print('Гражданство не подходит')
                    continue
                
                if oplata_filter(text):
                    print('Оплата не подходит')
                    continue
                
                if check_project_duration(text):
                    print('Маленькая продолжительность проекта')
                    
                    continue

                if has_strikethrough(msg):
                    print(f"❌ Сообщение {msg.id} содержит зачёркнутый текст — пропускаем")
                    continue
                
                try:
                    text_gpt = await process_vacancy(text)
                except Exception as e:
                    print(e)
                    continue

                if text_gpt == None or text_gpt == 'None':
                    continue

                try:
                    text = text_gpt.get("text")
                    if text is None:
                       print('Вакансия отсеяна')
                       continue
                    
                    vac_id = text_gpt.get('vacancy_id')
                    print(vac_id)
                    print(type(vac_id))
                    rate = text_gpt.get("rate")
                    vacancy = text_gpt.get('vacancy_title')
                    deadline_date = text_gpt.get("deadline_date")
                    deadline_time = text_gpt.get("deadline_time")
                    utochnenie = text_gpt.get("utochnenie")
                    if vacancy is None or vacancy == 'None':
                        print('нет вакансии')
                        continue
                     

                    # Вакансия отсекается, если нет ID
                    if vac_id is None  or vac_id == 'None':
                        print('Вакансия отсеяна, нет ID')
                        continue

                    # Блок для обработки ставки
                    if rate is None or int(rate) == 0:
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                    else:
                        rate = int(rate)
                        rate = round(rate / 5) * 5
                        print(rate)
                        
                        rate = find_rate_in_sheet_gspread(rate)
                        rate = re.sub(r'\s+', '', rate)
                        rounded = math.ceil(int(rate) / 100) * 100 
                        rate = f"{rounded:,}".replace(",", " ")
                        print(rate)

                        if rate is None or rate == 'None' or vacancy is None or vacancy == 'None':
                            print('нет вакансии')
                            continue
                        
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"
                                
                    if utochnenie == 'True' or utochnenie is True:
                        await telethon_client.send_message(
                            GROUP_ID,
                            text_cleaned,
                        )
                        continue
                        
                    forwarded_msg = await telethon_client.send_message(
                        dst_chat,
                        text_cleaned,
                        file=msg.media,
                        reply_to=dst_topic_id
                    )
                    
                    async with AsyncSessionLocal() as session:
                        await add_message_mapping(
                            session,
                            src_chat_id=src_chat,
                            src_msg_id=msg.id,
                            dst_chat_id=dst_chat,
                            dst_msg_id=forwarded_msg.id,
                            deadline_date=deadline_date,
                            deadline_time=deadline_time
                        )
                    
                    await asyncio.sleep(0.5)
            
                except Exception as e:
                    print(f'Ошибка при обработке и отправке: {e}')
                    continue
            
        except Exception as e:
            print(f"[!] Ошибка при чтении топика {src_topic_id} в чате {src_chat}: {e}")


def has_strikethrough(message):
    if not message.entities:
        return False
    for entity in message.entities:
        if entity.__class__.__name__ == 'MessageEntityStrike':
            print(f"🔍 Найден зачёркнутый текст в сообщении {message.id}")
            return True
    return False

async def register_handler(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal):
    @telethon_client.on(events.NewMessage(chats=CHANNELS))
    async def new_channel_message_handler(event):
        text_orig = event.message.message or ""
        if not text_orig:
            return

        if is_russia_only_citizenship(text):
                    print('Гражданство не подходит')
                    return

        # Проверка зачёркнутого текста
        if has_strikethrough(event.message):
            print(f"❌ Сообщение {event.message.id} в канале {event.chat_id} содержит зачёркнутый текст — пропускаем")
            return
        if oplata_filter(text):
                    print('Оплата не подходит')
                    return
        entity = await telethon_client.get_entity(int(GROUP_ID))
        
        try:
            text_gpt = await process_vacancy(text)
        except Exception as e:
            print(e)
            return
        if text_gpt == None:
            return
        else:
            try:
                        
                        
                        #text_gpt = json.loads(text_gpt)
                        text = text_gpt.get("text")
                        if text == None:
                           print('Вакансия отсеяна')
                           return
                        vac_id = text_gpt.get('vacancy_id')
                        print(vac_id)
                        rate = text_gpt.get("rate")
                        vacancy = text_gpt.get('vacancy_title')
                        
                        deadline_date = text_gpt.get("deadline_date")  # "DD.MM.YYYY"
                        deadline_time = text_gpt.get("deadline_time") 
                        
                         

                        if rate == None:
                            
                            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                            

                        if int(rate) == 0:
                           text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
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

                            if rate is None or vacancy is None:
                                return
                            else:
                                    
                                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: {rate} RUB\n\n{text}"

            except Exception as e:
                print(e)
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

            for mapping in mappings:
                try:
                    msg = await telethon_client.get_messages(mapping.src_chat_id, ids=mapping.src_msg_id)
                    
                    
                    if mapping.src_msg_id == 5456 or mapping.src_msg_id == '5456':
                       print(msg.text)
                    vacancy_id = None
                    if msg.message:
                        match = VACANCY_ID_REGEX.search(msg.message)
                        if match:
                            vacancy_id = match.group(0)

                    # Если сообщение удалено или зачёркнуто
                    if has_strikethrough(msg):
                        print(f"❌ Сообщение {mapping.src_msg_id} содержит зачёркнутый текст — удаляем")
                        await mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id
                        )
                        await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                        continue
                    stop_pattern = re.compile(r'(🛑.*СТОП.*🛑|(?:\bстоп\b))', re.IGNORECASE)
                    # Проверка на слово "стоп"
                    if msg.message and stop_pattern.search(msg.message):
                        print(f"🛑 Сообщение {mapping.src_msg_id} содержит слово 'стоп' — удаляем")
                        await mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id
                        )
                        await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                        continue

                    # Проверка дедлайна
                    if mapping.deadline_date:
                        try:
                            date_str = mapping.deadline_date.strip() if mapping.deadline_date else None
                            time_str = mapping.deadline_time.strip() if mapping.deadline_time else "23:59"

                            if not date_str or date_str.lower() == "none":
                                continue  # дата отсутствует, пропускаем

                            parts = date_str.split(".")
                            if len(parts) != 3:
                                raise ValueError(f"Некорректный формат даты: {date_str}")

                            day, month, year = parts
                            day = day.zfill(2)
                            month = month.zfill(2)

                            deadline_dt = datetime.strptime(f"{day}.{month}.{year} {time_str}", "%d.%m.%Y %H:%M")

                            print(f"🕒 Проверка дедлайна для {mapping.src_msg_id} "
                                  f"({mapping.src_chat_id}): {deadline_dt}")

                            now_utc = datetime.now(timezone.utc)
                            if deadline_dt.replace(tzinfo=timezone.utc) <= now_utc:
                                print(f"⏰ Дедлайн для сообщения {mapping.src_msg_id} истёк — удаляем")
                                await mark_inactive_and_schedule_delete(
                                    telethon_client, mapping, vacancy_id
                                )
                                await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                                continue

                        except Exception as e:
                            print(f"⚠ Ошибка парсинга дедлайна для {mapping.src_msg_id} "
                                  f"в {mapping.src_chat_id}: {e}")

                except FloodWaitError as e:
                    print(f"⚠ Flood control: ждём {e.seconds} сек.")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Ошибка проверки {mapping.src_msg_id} в {mapping.src_chat_id}: {e}")

        await asyncio.sleep(60)


async def mark_inactive_and_schedule_delete(client, mapping, vacancy_id):
    try:
        msg = await client.get_messages(mapping.dst_chat_id, ids=mapping.dst_msg_id)
        if not msg:
            return

        
        if vacancy_id:
            new_text = f"\n\n{vacancy_id} — вакансия неактивна"
        else:
            new_text = "Вакансия неактивна"

        await client.edit_message(mapping.dst_chat_id, mapping.dst_msg_id, new_text)

        # Закрепляем
        await client.pin_message(mapping.dst_chat_id, mapping.dst_msg_id, notify=False)
        print(f"📌 Закреплено сообщение {mapping.dst_msg_id} в {mapping.dst_chat_id}")

        # Ждём 24 часа
        await asyncio.sleep(24 * 60 * 60)

        # Открепляем и удаляем
        await client.unpin_message(mapping.dst_chat_id, mapping.dst_msg_id)
        await client.delete_messages(mapping.dst_chat_id, mapping.dst_msg_id)
        print(f"🗑 Удалено сообщение {mapping.dst_msg_id} в {mapping.dst_chat_id}")

    except FloodWaitError as e:
        print(f"⚠ Flood control: ждём {e.seconds} сек.")
        await asyncio.sleep(e.seconds)
        await mark_inactive_and_schedule_delete(client, mapping, vacancy_id)
    except Exception as e:
        print(f"Ошибка при изменении/удалении {mapping.dst_msg_id}: {e}")
  # проверяем каждую минуту
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
    print('Сканирование топиков включено')

    # Берём все уникальные чаты из TOPIC_MAP для подписки
    chats_to_watch = list({chat_id for chat_id, _ in TOPIC_MAP.keys()})

    @telethon_client.on(events.NewMessage(chats=chats_to_watch))
    async def new_topic_message(event):
        # На старом Telethon топики могут не поддерживаться
        # Ищем все ключи для этого чата
        key_candidates = [k for k in TOPIC_MAP if k[0] == event.chat_id]
        if not key_candidates:
            return  # Чат не отслеживаем

        # Берём первый ключ (единственный или любой)
        key = key_candidates[0]
        dst_chat_id, dst_topic_id = TOPIC_MAP[key]

        text = getattr(event.message, 'message', '') or ""
        if not text:
            return

        if is_russia_only_citizenship(text):
            print('Гражданство не подходит')
            return

        if has_strikethrough(event.message):
            print(f"❌ Сообщение {event.message.id} в канале {event.chat_id} содержит зачёркнутый текст — пропускаем")
            return

        if oplata_filter(text):
            print('Оплата не подходит')
            return
        if check_project_duration(text):
            print('Маленькая продолжительность проекта')
            asyncio.sleep(3)
            return
        try:
            text_gpt = await process_vacancy(text)
        except Exception as e:
            print(e)
            return

        if text_gpt is None or text_gpt == 'None':
            return

        try:
            text = text_gpt.get("text")
            if text == None or text == 'None':
                print('Вакансия отсеяна')
                return
            vac_id = text_gpt.get('vacancy_id')
            print(vac_id)
            rate = text_gpt.get("rate")
            vacancy = text_gpt.get('vacancy_title')
            if vacancy is None or vacancy == 'None':
                print('нет вакансии')
                return
            if vac_id is None or vac_id  == 'None':
                print('нет айди')
                return

            deadline_date = text_gpt.get("deadline_date")
            deadline_time = text_gpt.get("deadline_time")
            utochnenie = text_gpt.get("utochnenie")
            # Формируем текст для пересылки
            if not rate or int(rate) == 0:
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
            print(e)
            return
        try:
            if utochnenie:
                await telethon_client.send_message(
                    GROUP_ID,
                    message=text_cleaned,
                )
        except Exception as e:
            print(e)
            return
        try:
            forwarded_msg = await telethon_client.send_message(
                dst_chat_id,
                message=text_cleaned,
                parse_mode='html'
            )
        except Exception:
            forwarded_msg = await telethon_client.send_message(
                dst_chat_id,
                message=text_cleaned
            )

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

async def check_and_delete_duplicates(teleton_client, channel_id: int):
    """Проверяет последние сообщения канала на дубликаты по ID в тексте"""
    seen_ids = set()
    while True:
        try:
            async for message in teleton_client.iter_messages(channel_id):
                if not message.message:
                    continue
                
                match = VACANCY_ID_REGEX.search(message.message)
                if match:
                    vacancy_id = match.group(0)
                else:
                    continue

                if vacancy_id in seen_ids:
                    print(f"❌ Дубликат найден: {vacancy_id}, удаляю сообщение {message.id}")
                    await message.delete()
                else:
                    seen_ids.add(vacancy_id)
        except Exception as e:
            print('Ошибка при проверке', e)
        # очищаем сет в конце итерации
        seen_ids.clear()
        print("✅ Проверка завершена, set очищен")
        await asyncio.sleep(60)
