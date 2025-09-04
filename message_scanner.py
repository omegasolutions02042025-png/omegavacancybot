import asyncio
from datetime import datetime, timedelta, timezone
import math
import re
from telethon.errors import FloodWaitError
from db import add_message_mapping
from gpt import process_vacancy
from googlesheets import find_rate_in_sheet_gspread
from funcs import is_russia_only_citizenship, oplata_filter, check_project_duration
from message_handlers import has_strikethrough
from bot_utils import send_error_to_admin, update_activity
import os

GROUP_ID = os.getenv('GROUP_ID')

async def forward_recent_posts(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal):
    """Сканирует и пересылает недавние сообщения из каналов"""
    # aware-дата в UTC
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)

    entity = await telethon_client.get_entity(int(GROUP_ID))

    for source in CHANNELS:
        update_activity()
        
        async for message in telethon_client.iter_messages(source):
            # Если сообщение старше 2 недель — прекращаем итерацию
            if message.date < cutoff_date:
                break

            try:
                text_orig = message.message or ""
                if not text_orig:
                    continue
                
                if is_russia_only_citizenship(text_orig):
                    continue

                if has_strikethrough(message):
                    continue
                    
                if oplata_filter(text_orig):
                    continue
                    
                if check_project_duration(text_orig):
                    await asyncio.sleep(3)
                    continue
                    
                try:
                    text_gpt = await process_vacancy(text_orig)
                except Exception as e:
                    from main import bot
                    await send_error_to_admin(bot, str(e), "forward_recent_posts - process_vacancy")
                    continue
                    
                if text_gpt == None:
                    continue
                else:
                    try:
                        text = text_gpt.get("text")
                        if text == None:
                           continue            
                        vac_id = text_gpt.get('vacancy_id')
                        rate = text_gpt.get("rate")
                        vacancy = text_gpt.get('vacancy_title')
                        if vacancy is None:
                            continue
                                    
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
                        await send_error_to_admin(bot, str(e), "forward_recent_posts - message_processing")
                        continue

                forwarded_msg = await telethon_client.send_message(entity, text_cleaned)
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
                from main import bot
                await send_error_to_admin(bot, str(e), f"forward_recent_posts - source {source}")

async def forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=14):
    """Сканирует и пересылает сообщения из топиков"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    for (src_chat, src_topic_id), (dst_chat, dst_topic_id) in TOPIC_MAP.items():
        update_activity()
        
        try:
            async for msg in telethon_client.iter_messages(
                src_chat,
                reply_to=src_topic_id,
                reverse=False,
            ):
                if msg.date < cutoff_date:
                    await asyncio.sleep(5)
                    break
                
                text = msg.text
                if not text:
                    continue
                    
                if is_russia_only_citizenship(text):
                    continue
                
                if oplata_filter(text):
                    continue
                
                if check_project_duration(text):
                    continue

                if has_strikethrough(msg):
                    continue
                
                try:
                    text_gpt = await process_vacancy(text)
                except Exception as e:
                    from main import bot
                    await send_error_to_admin(bot, str(e), "forward_messages_from_topics - process_vacancy")
                    continue

                if text_gpt == None or text_gpt == 'None':
                    continue

                try:
                    text = text_gpt.get("text")
                    if text is None:
                       continue
                    
                    vac_id = text_gpt.get('vacancy_id')
                    rate = text_gpt.get("rate")
                    vacancy = text_gpt.get('vacancy_title')
                    deadline_date = text_gpt.get("deadline_date")
                    deadline_time = text_gpt.get("deadline_time")
                    utochnenie = text_gpt.get("utochnenie")
                    if vacancy is None or vacancy == 'None':
                        continue

                    # Вакансия отсекается, если нет ID
                    if vac_id is None  or vac_id == 'None':
                        continue

                    # Блок для обработки ставки
                    if rate is None or int(rate) == 0:
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}"
                    else:
                        rate = int(rate)
                        rate = round(rate / 5) * 5
                        
                        rate = find_rate_in_sheet_gspread(rate)
                        rate = re.sub(r'\s+', '', rate)
                        rounded = math.ceil(int(rate) / 100) * 100 
                        rate = f"{rounded:,}".replace(",", " ")

                        if rate is None or rate == 'None' or vacancy is None or vacancy == 'None':
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
                    from main import bot
                    await send_error_to_admin(bot, str(e), "forward_messages_from_topics - message_processing")
                    continue
            
        except Exception as e:
            from main import bot
            await send_error_to_admin(bot, str(e), f"forward_messages_from_topics - topic {src_topic_id} in chat {src_chat}")
