
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
from googlesheets import find_rate_in_sheet_gspread, search_and_extract_values
from typing import Tuple, Optional
from funcs import is_russia_only_citizenship, oplata_filter, check_project_duration
from telethon.errors import FloodWaitError
from aiogram import Bot
import teleton_client
import os

VACANCY_ID_REGEX = re.compile(
    r"(?:🆔\s*)?(?:[\w\-\u0400-\u04FF]+[\s\-]*)?\d+", 
    re.IGNORECASE
)
GROUP_ID = os.getenv('GROUP_ID')
ADMIN_ID = os.getenv('ADMIN_ID')

#
#
# --- Telethon функции ---

async def forward_recent_posts(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal, bot: Bot):
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
                
                if is_russia_only_citizenship(text_orig):
                    await bot.send_message(ADMIN_ID, f"❌ Сообщение {message.id} в канале {entity} содержит гражданство, не подлежащее рассмотрению — пропускаем")
                    continue

                if has_strikethrough(message):
                    await bot.send_message(ADMIN_ID, f"❌ Сообщение {message.id} в канале {entity} содержит зачёркнутый текст — пропускаем")
                    continue
                if oplata_filter(text_orig):
                    await bot.send_message(ADMIN_ID, f"❌ Сообщение {message.id} в канале {entity} содержит неподходящую оплату — пропускаем")
                    continue
                if check_project_duration(text_orig):
                    await bot.send_message(ADMIN_ID, f"❌ Сообщение {message.id} в канале {entity} содержит маленькую продолжительность проекта — пропускаем")
                    asyncio.sleep(3)
                    continue
                try:
                    text_gpt = await process_vacancy(text_orig)
                    #print(text)
                except Exception as e:
                    await bot.send_message(ADMIN_ID, f"❌ Ошибка при обработке вакансии {message.id} в канале {entity}: {e}")
                    continue
                if text_gpt == None:
                    continue
                else:


                    try:
                        text = text_gpt.get("text")
                        if text == None:
                           await bot.send_message(ADMIN_ID, f"❌ Вакансия отсеяна {message.id} в канале {entity}")
                           continue            
                        vac_id = text_gpt.get('vacancy_id')
                        await bot.send_message(ADMIN_ID, f"✅ Вакансия {vac_id} найдена в канале {entity}")
                        rate = text_gpt.get("rate")
                        vacancy = text_gpt.get('vacancy_title')
                        if vacancy is None:
                            await bot.send_message(ADMIN_ID, f"❌ Вакансия {vac_id} отсеяна в канале {entity}")
                            continue
                                    
                        deadline_date = text_gpt.get("deadline_date")  # "DD.MM.YYYY"
                        deadline_time = text_gpt.get("deadline_time") 
                                             

                        if int(rate) == 0 or rate == None:
                            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                        else:
                            rate = float(rate)
                            rate_sng_contract = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (штат/контракт) СНГ').get('B')
                            rate_sng_ip = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (ИП) СНГ').get('B')
                            rate_sng_samozanyatii = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (Самозанятый) СНГ').get('B')
                            if rate_sng_contract and rate_sng_ip and rate_sng_samozanyatii:
                                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до:\n штат/контракт : {rate_sng_contract} RUB,\n ИП : {rate_sng_ip} RUB,\n самозанятый : {rate_sng_samozanyatii} RUB\n\n{text}"
                            else:
                                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                    except Exception as e:
                        await bot.send_message(ADMIN_ID, f"❌ Ошибка при формировании текста вакансии {message.id} в канале {entity}: {e}")
                        continue

                forwarded_msg = await telethon_client.send_message(entity, text_cleaned)
                await bot.send_message(ADMIN_ID, f"✅ Переслал из {source}: {message.id}")
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
                await bot.send_message(ADMIN_ID, f"❌ Ошибка при пересылке из {source}: {e}")



async def forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot : Bot, days=14):
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    await bot.send_message(ADMIN_ID, f"[i] Берем сообщения с {cutoff_date}")

    for (src_chat, src_topic_id), (dst_chat, dst_topic_id) in TOPIC_MAP.items():
        await bot.send_message(ADMIN_ID, f"[i] Проверяем топик {src_topic_id} в чате {src_chat}")
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
                    await bot.send_message(ADMIN_ID, f'❌ Гражданство не подходит в сообщении {msg.id}')
                    continue
                
                if oplata_filter(text):
                    await bot.send_message(ADMIN_ID, f'❌ Оплата не подходит в сообщении {msg.id}')
                    continue
                
                if check_project_duration(text):
                    await bot.send_message(ADMIN_ID, f'❌ Маленькая продолжительность проекта в сообщении {msg.id}')
                    continue

                if has_strikethrough(msg):
                    await bot.send_message(ADMIN_ID, f"❌ Сообщение {msg.id} содержит зачёркнутый текст — пропускаем")
                    continue
                
                try:
                    text_gpt = await process_vacancy(text)
                except Exception as e:
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка в GPT в сообщении {msg.id}: {e}')
                    continue

                if text_gpt == None or text_gpt == 'None':
                    await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в сообщении {msg.id}')
                    continue

                try:
                    text = text_gpt.get("text")
                    if text is None:
                        await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в сообщении {msg.id}')
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
                        await bot.send_message(ADMIN_ID, f'❌ Нет вакансии в GPT в сообщении {msg.id}')
                        continue
                     

                    # Вакансия отсекается, если нет ID
                    if vac_id is None  or vac_id == 'None':
                        await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна, нет ID в сообщении {msg.id}')
                        continue

                    # Блок для обработки ставки
                    if rate is None or int(rate) == 0:
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                    else:
                        rate = float(rate)
                        rate_sng_contract = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (штат/контракт) СНГ').get('B')
                        rate_sng_ip = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (ИП) СНГ').get('B')
                        rate_sng_samozanyatii = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (Самозанятый) СНГ').get('B')
                        if rate_sng_contract and rate_sng_ip and rate_sng_samozanyatii:
                            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до:\n штат/контракт : {rate_sng_contract} RUB,\n ИП : {rate_sng_ip} RUB,\n самозанятый : {rate_sng_samozanyatii} RUB\n\n{text}"
                        else:
                            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                        
                    if utochnenie == 'True' or utochnenie is True:
                        await telethon_client.send_message(
                            GROUP_ID,
                            text_cleaned,
                        )
                        await bot.send_message(ADMIN_ID, f'✅ Вакансия отправлена в группу в сообщении {msg.id}')
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
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке и отправке в сообщении {msg.id}: {e}')
                    continue
            
        except Exception as e:
            await bot.send_message(ADMIN_ID, f"[!] Ошибка при чтении топика {src_topic_id} в чате {src_chat}: {e}")
    

def has_strikethrough(message):
    if not message.entities:
        return False
    for entity in message.entities:
        if entity.__class__.__name__ == 'MessageEntityStrike':
            print(f"🔍 Найден зачёркнутый текст в сообщении {message.id}")
            return True
    return False

async def register_handler(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal, bot : Bot):
    @telethon_client.on(events.NewMessage(chats=CHANNELS))
    async def new_channel_message_handler(event):
        text = event.message.message or event.message.text or ""
        if not text:
            return

        if is_russia_only_citizenship(text):
            await bot.send_message(ADMIN_ID, f'❌ Гражданство не подходит в сообщении {event.message.id}')
            return

        # Проверка зачёркнутого текста
        if has_strikethrough(event.message):
            await bot.send_message(ADMIN_ID, f"❌ Сообщение {event.message.id} в канале {event.chat_id} содержит зачёркнутый текст — пропускаем")
            return
        if oplata_filter(text):
            await bot.send_message(ADMIN_ID, f'❌ Оплата не подходит в сообщении {event.message.id}')
            return
        entity = await telethon_client.get_entity(int(GROUP_ID))
        
        try:
            text_gpt = await process_vacancy(text)
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке вакансии в сообщении {event.message.id}: {e}')
            return
        if text_gpt == None:
            return
        else:
            try:
                
                text = text_gpt.get("text")
                if text == None:
                   await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в сообщении {event.message.id}')
                   return
                vac_id = text_gpt.get('vacancy_id')
                print(vac_id)
                rate = text_gpt.get("rate")
                vacancy = text_gpt.get('vacancy_title')
                deadline_date = text_gpt.get("deadline_date")  # "DD.MM.YYYY"
                deadline_time = text_gpt.get("deadline_time") 
                if rate == None or int(rate) == 0:
                    text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                else:
                    rate = float(rate)
                    rate_sng_contract = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (штат/контракт) СНГ').get('B')
                    rate_sng_ip = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (ИП) СНГ').get('B')
                    rate_sng_samozanyatii = search_and_extract_values('M', rate, ['B'], 'Рассчет ставки (Самозанятый) СНГ').get('B')
                    if rate_sng_contract and rate_sng_ip and rate_sng_samozanyatii:
                        
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до:\n штат/контракт : {rate_sng_contract} RUB,\n ИП : {rate_sng_ip} RUB,\n самозанятый : {rate_sng_samozanyatii} RUB\n\n{text}"
                    else:
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
            except Exception as e:
                await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке вакансии в сообщении {event.message.id}: {e}')
                return
        try:
            forwarded_msg = await telethon_client.send_message(entity=entity, message=text_cleaned)
        except Exception:
            forwarded_msg = await telethon_client.send_message(entity=entity, message=text_cleaned, parse_mode='html')

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

        await bot.send_message(ADMIN_ID, f'✅ Вакансия добавлена в группу в сообщении {event.message.id}')

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


async def register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot : Bot):
    print('Сканирование топиков включено')

    # Берём все уникальные чаты из TOPIC_MAP для подписки
    chats_to_watch = list({chat_id for chat_id, _ in TOPIC_MAP.keys()})

    @telethon_client.on(events.NewMessage(chats=chats_to_watch))
    async def new_topic_message(event):
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
            await bot.send_message(ADMIN_ID, f'❌ Гражданство не подходит в топике {src_topic_id} в чате {event.chat_id}')
            return

        if has_strikethrough(event.message):
            await bot.send_message(ADMIN_ID, f"❌ Сообщение {event.message.id} содержит зачёркнутый текст — пропускаем")
            return

        if oplata_filter(text):
            await bot.send_message(ADMIN_ID, f'❌ Оплата не подходит в топике {src_topic_id} в чате {event.chat_id}')
            return

        if check_project_duration(text):
            await bot.send_message(ADMIN_ID, f'❌ Маленькая продолжительность проекта в топике {src_topic_id} в чате {event.chat_id}')
            return

        try:
            text_gpt = await process_vacancy(text)
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке вакансии в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return

        if text_gpt is None or text_gpt == 'None':
            return

        try:
            text = text_gpt.get("text")
            if text == None or text == 'None':
                await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в топике {src_topic_id} в чате {event.chat_id}')
                return
            vac_id = text_gpt.get('vacancy_id')
            rate = text_gpt.get("rate")
            vacancy = text_gpt.get('vacancy_title')
            if vacancy is None or vacancy == 'None':
                await bot.send_message(ADMIN_ID, f'❌ Нет вакансии в топике {src_topic_id} в чате {event.chat_id}')
                return
            if vac_id is None or vac_id == 'None':
                await bot.send_message(ADMIN_ID, f'❌ Нет айди в топике {src_topic_id} в чате {event.chat_id}')
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
            await bot.send_message(ADMIN_ID, f'❌ Ошибка обработки данных вакансии в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return

        try:
            if utochnenie == 'True' or utochnenie is True:
                await telethon_client.send_message(
                    GROUP_ID,
                    message=text_cleaned,
                )
                return  # Если отправили в группу уточнений, не отправляем в канал
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка отправки в группу уточнений в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return

        try:
            forwarded_msg = await telethon_client.send_message(
                dst_chat_id,
                message=text_cleaned,
                parse_mode='html',
                reply_to=dst_topic_id
            )
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Не удалось отправить в канал в топике {src_topic_id} в чате {event.chat_id}: {e}')
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
            await bot.send_message(ADMIN_ID, f'✅ Вакансия добавлена в канал в топике {src_topic_id} в чате {event.chat_id}')


async def check_and_delete_duplicates(teleton_client, channel_id: int, bot: Bot, topic_map: dict):
    """Проверяет последние сообщения канала на дубликаты по ID в тексте"""
    seen_ids = set()
    
    target_topics = [v[1] for v in topic_map.values()]
    print(target_topics)
    while True:
        try:
            for topic_id in target_topics:
                
                async for message in teleton_client.iter_messages(channel_id, reply_to=topic_id):
                    if not message.text:
                        continue
                    
                    match = VACANCY_ID_REGEX.search(message.text)
                    if match:
                        vacancy_id = match.group(0).strip()
                        
                    else:
                        continue

                    if vacancy_id in seen_ids:
                        await bot.send_message(ADMIN_ID, f'❌ Дубликат найден: {vacancy_id}, удаляю сообщение {message.id} в канале {channel_id}')
                        await message.delete()
                    else:
                        seen_ids.add(vacancy_id)
        except Exception as e:
            print('Ошибка при проверке', e)
        # очищаем сет в конце итерации
        seen_ids.clear()
        print("✅ Проверка завершена, set очищен")
        await asyncio.sleep(60)


async def cleanup_by_striked_id(telethon_client, src_chat_id, dst_chat_id):
    """
    src_chat_id — канал-источник, откуда берём айди
    dst_chat_id — канал, где ищем зачёркнутый айди
    """
    async for msg in telethon_client.iter_messages(src_chat_id):
        try:
            if not msg.message or not msg.text:
                continue
            
            text = msg.message or msg.text
            # Ищем vacancy_id по regex
            match = VACANCY_ID_REGEX.search(text)
            if not match:
                continue

            vacancy_id = match.group(0)
            
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            name_vac = lines[1] if len(lines) > 1 else None
            

            # Ищем в другом канале это зачёркнутое айди
            async for dst_msg in telethon_client.iter_messages(dst_chat_id, search=vacancy_id):
                
                if dst_msg.message and vacancy_id in dst_msg.message:
                    if has_strikethrough(dst_msg):
                        print(f"🗑 Найден зачеркнутый ID {vacancy_id} в {dst_chat_id} → удаляем сообщение {msg.id} из {src_chat_id}")
                        await mark_as_deleted(telethon_client, msg.id, src_chat_id, vacancy_id, name_vac)
                        break  # нашли и удалили → идём к следующему

        except FloodWaitError as e:
            print(f"⚠ Flood control: ждём {e.seconds} сек.")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"Ошибка обработки сообщения {msg.id}: {e}")
        
    await asyncio.sleep(500)


async def mark_as_deleted(client, msg_id, chat_id, vacancy_id, name_vac):
    try:
        
        if vacancy_id:
            new_text = f"\n\n{vacancy_id} — вакансия неактивна\n{name_vac}"
        else:
            new_text = "Вакансия неактивна"

        await client.edit_message(chat_id, msg_id, new_text)

        # Закрепляем
        await client.pin_message(chat_id, msg_id, notify=False)
        print(f"📌 Закреплено сообщение {msg_id}")

        # Ждём 24 часа
        await asyncio.sleep(24 * 60 * 60)

        # Открепляем и удаляем
        await client.unpin_message(chat_id, msg_id)
        await client.delete_messages(chat_id, msg_id)
        print(f"🗑 Удалено сообщение {msg_id}")

    except Exception as e:
        print(f"Ошибка при изменении/удалении {msg_id}: {e}")
  # проверяем каждую минуту
    await asyncio.sleep(20)