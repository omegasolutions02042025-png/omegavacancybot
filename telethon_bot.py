
import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import re
import random
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User
from db import get_all_channels, add_message_mapping, remove_message_mapping, get_all_message_mappings, get_next_sequence_number
from googlesheets import find_rate_in_sheet_gspread, search_and_extract_values
from typing import Tuple, Optional
from funcs import is_russia_only_citizenship, oplata_filter, check_project_duration, send_mess_to_group, get_message_datetime, extract_vacancy_id_and_text, remove_vacancy_id
from telethon.errors import FloodWaitError
from aiogram import Bot
import teleton_client
import os
from gpt_gimini import process_vacancy_with_gemini, format_vacancy_gemini
from kb import scan_vac_kb
from telethon_monitor import has_strikethrough

VACANCY_ID_REGEX = re.compile(
    r"(?:🆔\s*)?(?:[\w\-\u0400-\u04FF]+[\s\-]*)?\d+", 
    re.IGNORECASE
)
GROUP_ID = os.getenv('GROUP_ID')
ADMIN_ID = os.getenv('ADMIN_ID')
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")



telethon_client = TelegramClient('dmitryi', API_ID, API_HASH)

async def forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot : Bot, days=14):
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    await bot.send_message(ADMIN_ID, f"[i] Берем сообщения с {cutoff_date}")

    for (src_chat, src_topic_id), (dst_chat, dst_topic_id) in TOPIC_MAP.items():
        await bot.send_message(ADMIN_ID, f"[i] Проверяем топик {src_topic_id} в чате {src_chat}")
        try:
            msgs = []
            async for msg in telethon_client.iter_messages(
                src_chat,
                reply_to=src_topic_id,
                reverse=True,

            ):
                if msg.date >= cutoff_date:
                    msgs.append(msg)
            msgs.sort(key=lambda m: m.date)
            
            for msg in msgs:
                text = msg.text
                if not text:
                    continue
                
                if check_project_duration(text):
                    await bot.send_message(ADMIN_ID, f'❌ Маленькая продолжительность проекта в сообщении {msg.id}')
                    continue

                if has_strikethrough(msg):
                    await bot.send_message(ADMIN_ID, f"❌ Сообщение {msg.id} содержит зачёркнутый текст — пропускаем")
                    continue
                
                try:
                    text_gpt = await process_vacancy_with_gemini(text)
                except Exception as e:
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка в GPT в сообщении {msg.id}: {e}')
                    continue
                
                reason = text_gpt.get("reason")
                if reason:
                    await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в сообщении {msg.id}: {reason}')
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
                    rate = text_gpt.get("rate")
                    vacancy = text_gpt.get('vacancy_title')
                    deadline_date = text_gpt.get("deadline_date")
                    deadline_time = text_gpt.get("deadline_time")
                    utochnenie = text_gpt.get("utochnenie")
                    delay_payment = text_gpt.get("delay_payment")
                    acts = text_gpt.get("acts")
                    only_fulltime = text_gpt.get("only_fulltime")
                    short_project = text_gpt.get("short_project")
                    long_payment = text_gpt.get("long_payment")
                    message_date = f'Дата публикации: {get_message_datetime(msg)}'
                    rf_loc = text_gpt.get("rf_loc")
                    rb_loc = text_gpt.get("rb_loc")
                    
                    if vacancy is None or vacancy == 'None':
                        await bot.send_message(ADMIN_ID, f'❌ Нет вакансии в GPT в сообщении {msg.id}')
                        continue
                     

                    # Вакансия отсекается, если нет ID
                    if vac_id is None  or vac_id == 'None':
                        await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна, нет ID в сообщении {msg.id}')
                        continue

                    # Блок для обработки ставки
                    if delay_payment:
                        delay_payment_text = f"С отсрочкой платежа {delay_payment}после подписания акта:\n"
                        no_rate_delay = f'Условия оплаты: {delay_payment}'
                    else:
                        delay_payment_text = 'С отсрочкой платежа "35 рабочих дней" после подписания акта:\n'
                        no_rate_delay = 'Условия оплаты: Срок уточняется'
        
        
        
        
        # Блок для обработки ставки
                    if rate is None or int(rate) == 0:
        # если ставки нет — общий текст
                        text_cleaned = (
                            f"🆔{vac_id}\n\n"
                            f"{vacancy}\n\n"
                            f"Месячная ставка (на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n"
                            f"{no_rate_delay}\n\n"
                            f"{text}"
                                            )
                    else:
                        rate = int(rate)
                        rate_rf_contract = None
                        rate_rf_ip = None
                        rate_rb_contract = None
                        rate_rb_ip = None

                        # --- варианты для РФ ---
                        if rf_loc:
                            rate_rf_contract = await search_and_extract_values(
                                'K', rate, ['B'], 'Расчет ставки (штат) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                            )
                            rate_rf_ip = await search_and_extract_values(
                                'K', rate, ['B', 'J'], 'Расчет ставки (ИП) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                            )

                        # --- варианты для РБ ---
                        if rb_loc:
                            rate_rb_contract = await search_and_extract_values(
                                'M', rate, ['B'], 'Расчет ставки (штат/контракт) СНГ'
                            )
                            rate_rb_ip = await search_and_extract_values(
                                'N', rate, ['B', 'L'], 'Расчет ставки (Самозанятый/ИП) СНГ'
                            )

                        # --- объединённая логика оформления ---
                        def build_salary_block(flag_rf=False, flag_rb=False):
                            """Внутренняя функция для форматирования текста ставок"""
                            flag_text = "🇷🇺" if flag_rf else "🇧🇾"
                            region = "РФ" if flag_rf else "РБ"

                            # выбираем нужные пары
                            contract_data = rate_rf_contract if flag_rf else rate_rb_contract
                            ip_data = rate_rf_ip if flag_rf else rate_rb_ip

                            if not contract_data or not ip_data:
                                return (
                                    f"{flag_text}💰 Месячная ставка для юр лица {region}: "
                                    f"смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n"
                                )

                            rate_contract = contract_data.get('B')
                            rate_ip = ip_data.get('B')
                            gross = None
                            if ip_data.get('L'):
                                gross = ip_data.get('L')
                            else:
                                gross = ip_data.get('J')

                            # округляем IP/самозанятый до 1000
                            try:
                                rounded = (int(rate_ip) // 1000) * 1000
                                rate_ip = f"{rounded:,}".replace(",", " ")
                            except Exception:
                                pass

                            # форматы актирования и зачёркиваний
                            if acts:
                                acts_text = "Актирование: поквартальное\n"
                                state_contract_text = (
                                    f"<s>Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                                    f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)</s>"
                                )
                            else:
                                acts_text = "Актирование: ежемесячное\n"
                                state_contract_text = (
                                    f"Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                                    f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)"
                                )

                            # зачёркивания по условиям
                            if short_project or long_payment:
                                state_contract_text = f"<s>{state_contract_text}</s>"

                            if only_fulltime:
                                ip_text = f"<s>Вариант 2. Выплата ИП/Самозанятый: {rate_ip} RUB</s>"
                            else:
                                ip_text = f"Вариант 2. Выплата ИП/Самозанятый: {rate_ip} RUB"

                            return (
                                f"{flag_text}"
                                f"💰 Месячная ставка для юр лица {region}:\n"
                                f"{state_contract_text}\n"
                                f"{delay_payment_text}{acts_text}{gross} RUB/час (Gross)\n"
                                f"{ip_text}\n"
                            )

                        # --- итоговое формирование ---
                        salary_text = ""

                        if rf_loc and rb_loc:
                            # обе страны
                            salary_text = build_salary_block(flag_rb=True) + "\n" + build_salary_block(flag_rf=True)
                        elif rf_loc:
                            # только РФ
                            salary_text = build_salary_block(flag_rf=True)
                        elif rb_loc:
                            # только РБ
                            salary_text = build_salary_block(flag_rb=True)
                        else:
                            # ни одна не указана
                            salary_text = (
                                "💰 Месячная ставка: смотрим ваши предложения "
                                "(приоритет на минимальную)\n\n"
                                f"{no_rate_delay}\n"
                            )
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\n{salary_text}\n{text}"
                    formatted_text = await format_vacancy_gemini(text_cleaned, vac_id, message_date)
                        
                    if utochnenie == 'True' or utochnenie is True:
                        await bot.send_message(ADMIN_ID, "Отправлено для уточнения")
                        await bot.send_message(ADMIN_ID, formatted_text)
                        continue
                    try:                 
                        mess = await bot.send_message(chat_id=dst_chat, text='.', message_thread_id=dst_topic_id)
                        cleaned_text = remove_vacancy_id(formatted_text)
                        url = f"https://t.me/omega_vacancy_bot?start={mess.message_id}_{vac_id}"
                        ms_text = f"<a href='{url}'>{vac_id}</a>\n{cleaned_text}"
                        forwarded_msg = await bot.edit_message_text(
                            chat_id=dst_chat,
                            message_id=mess.message_id,
                            text=ms_text,
                            parse_mode='HTML',
                        )
            
                    except Exception as e:
                        await bot.send_message(ADMIN_ID, f'❌ Ошибка при отправке в сообщении {msg.id}: {e}')
                        continue
                    await send_mess_to_group(GROUP_ID, formatted_text, vac_id, bot)
                    
                                
                    async with AsyncSessionLocal() as session:
                        await add_message_mapping(
                            session,
                            src_chat_id=src_chat,
                            src_msg_id=msg.id,
                            dst_chat_id=dst_chat,
                            dst_msg_id=forwarded_msg.message_id,
                            deadline_date=deadline_date,
                            deadline_time=deadline_time
                        )
                                
                
                except Exception as e:
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке и отправке в сообщении {msg.id}: {e}')
                    continue
            
        except Exception as e:
            await bot.send_message(ADMIN_ID, f"[!] Ошибка при чтении топика {src_topic_id} в чате {src_chat}: {e}")
    




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

        if has_strikethrough(event.message):
            await bot.send_message(ADMIN_ID, f"❌ Сообщение {event.message.id} содержит зачёркнутый текст — пропускаем")
            return

        if check_project_duration(text):
            await bot.send_message(ADMIN_ID, f'❌ Маленькая продолжительность проекта в топике {src_topic_id} в чате {event.chat_id}')
            return

        try:
            text_gpt = await process_vacancy_with_gemini(text)
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке вакансии в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return
        
        reason = text_gpt.get("reason")
        if reason:
            await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в топике {src_topic_id} в чате {event.chat_id}: {reason}')
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
            delay_payment = text_gpt.get("delay_payment")
            acts = text_gpt.get("acts")
            only_fulltime = text_gpt.get("only_fulltime")
            short_project = text_gpt.get("short_project")
            long_payment = text_gpt.get("long_payment")
            message_date = f"Дата публикации: {get_message_datetime(event.message)}"
            location = text_gpt.get("location")
            rf_loc = False
            rb_loc = False
            for loc in location:
                if loc == 'РФ':
                    rf_loc = True
                elif loc == 'РБ':
                    rb_loc = True
            
            # Исправляем логику обработки ставки
            if rate is None or rate == 'None' or int(rate) == 0:
                text_cleaned = f"🆔{vac_id}\n\n{message_date}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{text}\n\n{message_date}"
            if delay_payment:
                delay_payment_text = f"С отсрочкой платежа {delay_payment}после подписания акта:\n"
                no_rate_delay = f'Условия оплаты: {delay_payment}'
            else:
                delay_payment_text = 'С отсрочкой платежа "35 рабочих дней" после подписания акта:\n'
                no_rate_delay = 'Условия оплаты: Срок уточняется'
            
            if rate is None or int(rate) == 0:
        # если ставки нет — общий текст
                text_cleaned = (
                    f"🆔{vac_id}\n\n"
                    f"{vacancy}\n\n"
                    f"Месячная ставка (на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n"
                    f"{no_rate_delay}\n\n"
                    f"{text}"
                                    )
            else:
                rate = int(rate)
                rate_rf_contract = None
                rate_rf_ip = None
                rate_rb_contract = None
                rate_rb_ip = None

                # --- варианты для РФ ---
                if rf_loc:
                    rate_rf_contract = await search_and_extract_values(
                        'K', rate, ['B'], 'Расчет ставки (штат) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                    )
                    rate_rf_ip = await search_and_extract_values(
                        'K', rate, ['B', 'J'], 'Расчет ставки (ИП) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                    )

                # --- варианты для РБ ---
                if rb_loc:
                    rate_rb_contract = await search_and_extract_values(
                        'M', rate, ['B'], 'Расчет ставки (штат/контракт) СНГ'
                    )
                    rate_rb_ip = await search_and_extract_values(
                        'N', rate, ['B', 'L'], 'Расчет ставки (Самозанятый/ИП) СНГ'
                    )

                # --- объединённая логика оформления ---
                def build_salary_block(flag_rf=False, flag_rb=False):
                    """Внутренняя функция для форматирования текста ставок"""
                    flag_text = "🇷🇺" if flag_rf else "🇧🇾"
                    region = "РФ" if flag_rf else "РБ"

                    # выбираем нужные пары
                    contract_data = rate_rf_contract if flag_rf else rate_rb_contract
                    ip_data = rate_rf_ip if flag_rf else rate_rb_ip

                    if not contract_data or not ip_data:
                        return (
                            f"{flag_text}💰 Месячная ставка для юр лица {region}: "
                            f"смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n"
                        )

                    rate_contract = contract_data.get('B')
                    rate_ip = ip_data.get('B')
                    gross = None
                    if ip_data.get('L'):
                        gross = ip_data.get('L')
                    else:
                        gross = ip_data.get('J')

                    # округляем IP/самозанятый до 1000
                    try:
                        rounded = (int(rate_ip) // 1000) * 1000
                        rate_ip = f"{rounded:,}".replace(",", " ")
                    except Exception:
                        pass

                    # форматы актирования и зачёркиваний
                    if acts:
                        acts_text = "Актирование: поквартальное\n"
                        state_contract_text = (
                            f"<s>Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                            f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)</s>"
                        )
                    else:
                        acts_text = "Актирование: ежемесячное\n"
                        state_contract_text = (
                            f"Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                            f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)"
                        )

                    # зачёркивания по условиям
                    if short_project or long_payment:
                        state_contract_text = f"<s>{state_contract_text}</s>"

                    if only_fulltime:
                        ip_text = f"<s>Вариант 2. Выплата ИП/Самозанятый: {rate_ip} RUB</s>"
                    else:
                        ip_text = f"Вариант 2. Выплата ИП/Самозанятый: {rate_ip} RUB"

                    return (
                        f"{flag_text}💰 Месячная ставка для юр лица {region}:\n"
                        f"{state_contract_text}\n"
                        f"{delay_payment_text}{acts_text}{gross} RUB/час (Gross)\n"
                        f"{ip_text}\n"
                    )

                # --- итоговое формирование ---
                salary_text = ""

                if rf_loc and rb_loc:
                    # обе страны
                    salary_text = build_salary_block(flag_rb=True) + "\n" + build_salary_block(flag_rf=True)
                elif rf_loc:
                    # только РФ
                    salary_text = build_salary_block(flag_rf=True)
                elif rb_loc:
                    # только РБ
                    salary_text = build_salary_block(flag_rb=True)
                else:
                    # ни одна не указана
                    salary_text = (
                        "💰 Месячная ставка: смотрим ваши предложения "
                        "(приоритет на минимальную)\n\n"
                        f"{no_rate_delay}\n"
                    )
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\n{salary_text}\n{text}"
                
            formatted_text = await format_vacancy_gemini(text_cleaned, vac_id, message_date)   
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка обработки данных вакансии в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return

        try:
            if utochnenie == 'True' or utochnenie is True:
                await bot.send_message(ADMIN_ID, "Отправлено для уточнения")
                await bot.send_message(ADMIN_ID, formatted_text)
                return  # Если отправили в группу уточнений, не отправляем в канал
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка отправки в группу уточнений в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return

        try:
            mess = await bot.send_message(chat_id=dst_chat_id, text='.', message_thread_id=dst_topic_id)
            cleaned_text = remove_vacancy_id(formatted_text)
            url = f"https://t.me/omega_vacancy_bot?start={mess.message_id}_{vac_id}"
            ms_text = f"<a href='{url}'>{vac_id}</a>\n{cleaned_text}"
            forwarded_msg = await bot.edit_message_text(
                chat_id=dst_chat_id,
                message_id=mess.message_id,
                text=ms_text,
                parse_mode='HTML',
            )
            
            await send_mess_to_group(GROUP_ID, formatted_text, vac_id, bot)
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
                dst_msg_id=forwarded_msg.message_id,
                deadline_date=deadline_date,
                deadline_time=deadline_time
            )
            await bot.send_message(ADMIN_ID, f'✅ Вакансия добавлена в канал в топике {src_topic_id} в чате {event.chat_id}')


async def send_message_by_username(username: str, text: str):
        try:
            # username можно писать без "@"
            if username.startswith("@"):
                username = username[1:]
            
            entity = await telethon_client.get_entity(username)
            await telethon_client.send_message(entity, text)
            print(f"✅ Сообщение отправлено пользователю @{username}")
            return True
        except Exception as e:
            print(f"❌ Ошибка при отправке @{username}: {e}")
            return False
        