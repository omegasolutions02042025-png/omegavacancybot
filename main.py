import asyncio

from telethon import TelegramClient



from db import (
    init_db,
    add_channel,
    remove_channel,
    get_all_channels,
    AsyncSessionLocal,
)

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from kb import main_kb, send_kb
from telethon_bot import *
from funcs import update_channels_and_restart_handler
import os
from dotenv import load_dotenv
from funcs import *
from gpt import process_vacancy, format_vacancy
from gpt_gimini import process_vacancy_with_gemini, format_vacancy_gemini
from googlesheets import find_rate_in_sheet_gspread, search_and_extract_values
from telethon_monitor import has_strikethrough, cleanup_by_striked_id, check_and_delete_duplicates, list_all_dialogs , monitor_and_cleanup, check_old_messages_and_mark

load_dotenv()

# Вставь свои данные
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
print(PHONE_NUMBER)
print(API_ID)
GROUP_ID = os.getenv("GROUP_ID")
current_handler = None  # Храним текущий обработчик
ADMIN_ID = os.getenv("ADMIN_ID")
# --- Aiogram бот ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- Telethon клиент ---
telethon_client = TelegramClient('dmitryi', API_ID, API_HASH)
##213123131



# --- FSM States ---
class AddChannel(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()

class ScanHand(StatesGroup):
    waiting_for_hand = State()
    waiting_for_topic = State()


TOPIC_MAP = {
    (-1002189931727, 3): (-1002658129391, 4),
    (-1002189931727, 1): (-1002658129391, 1),
    (-1002189931727, 14): (-1002658129391, 6),
    (-1002189931727, 5): (-1002658129391, 9),
    (-1002189931727, 8): (-1002658129391, 11),
    (-1002189931727, 20): (-1002658129391, 13),
    (-1002189931727, 25): (-1002658129391, 15),
    (-1002189931727, 16): (-1002658129391, 17),
    (-1002189931727, 12): (-1002658129391, 19),
    (-1002189931727, 27): (-1002658129391, 21),
    (-1002189931727, 1573): (-1002658129391, 23),
    (-1002189931727, 22): (-1002658129391, 25),
    (-1002189931727, 29): (-1002658129391, 27),
    (-1002189931727, 18): (-1002658129391, 29),
   
    

}




# --- Aiogram Handlers ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.from_user.id not in [6264939461, 429765805]:
        return
    await message.answer(text="Основное меню", reply_markup = await main_kb())



@dp.callback_query(F.data == 'scan_redlab')
async def scan_redlab(calback : CallbackQuery):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=14, bot = bot)

@dp.callback_query(F.data == 'scan_redlab_day')
async def scan_redlab(calback : CallbackQuery):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=1, bot = bot)
    
@dp.callback_query(F.data == 'scan_redlab_21')
async def scan_redlab(calback : CallbackQuery):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=21, bot = bot)





@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(text="Основное меню", reply_markup = await main_kb())



@dp.callback_query(F.data == 'scan_hand')
async def scan_hand(calback : CallbackQuery, state: FSMContext):
    await calback.message.answer('Отправьте вакансию для проверки')
    await state.set_state(ScanHand.waiting_for_hand)
    


@dp.message(ScanHand.waiting_for_hand)
async def scan_hand_message(message: types.Message, state: FSMContext):
    text = message.text
    if not text:
        await message.answer('Нет текста')
        return
    if is_russia_only_citizenship(text):
        await message.answer('Гражданство не подходит')
        return

    if check_project_duration(text):
        await message.answer('Маленькая продолжительность проекта')
        
        return

    try:
        text_gpt = await process_vacancy_with_gemini(text)
        print(text_gpt) 
    except Exception as e:
        await message.answer('Ошибка при обработке вакансии')
        return

    if text_gpt == None or text_gpt == 'None':
        await message.answer('Вакансия отсеяна')
        return

    try:
        text = text_gpt.get("text")
        if text is None:
            await message.answer('Вакансия отсеяна')
            return
        
        vac_id = text_gpt.get('vacancy_id')
        rate = text_gpt.get("rate")
        vacancy = text_gpt.get('vacancy_title')
        deadline_date = text_gpt.get("deadline_date")
        deadline_time = text_gpt.get("deadline_time")
        utochnenie = text_gpt.get("utochnenie")
        short_project = text_gpt.get("short_project")
        delay_payment = text_gpt.get("delay_payment")
        acts = text_gpt.get("acts")
        only_fulltime = text_gpt.get("only_fulltime")
        short_project = text_gpt.get("short_project")
        long_payment = text_gpt.get("long_payment")
        
        
        
        if vacancy is None or vacancy == 'None':
            await message.answer('Вакансия отсеяна')
            return
        

        # Вакансия отсекается, если нет ID
        if vac_id is None  or vac_id == 'None':
            await message.answer('Вакансия отсеяна, нет ID')
            return
        if delay_payment:
            delay_payment_text = f"С отсрочкой платежа {delay_payment}после подписания акта:\n"
            no_rate_delay = f'Условия оплаты: {delay_payment}'
        else:
            delay_payment_text = 'С отсрочкой платежа "Срок уточняется" после подписания акта:\n'
            no_rate_delay = 'Условия оплаты: Срок уточняется'
        
        
        
        # Блок для обработки ставки
        if rate is None or int(rate) == 0:
            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n\n{text}"
        else:
            rate = float(rate)
            rate_sng_contract = search_and_extract_values('M', rate, ['B'], 'Расчет ставки (штат/контракт) СНГ').get('B')
            rate_sng_ip = search_and_extract_values('M', rate, ['B'], 'Расчет ставки (ИП) СНГ').get('B')
            rate_sng_samozanyatii = search_and_extract_values('M', rate, ['B'], 'Расчет ставки (Самозанятый) СНГ').get('B')
            if rate_sng_contract and rate_sng_ip and rate_sng_samozanyatii:
                if acts:
                    acts_text = f"Актирование: поквартальное\n"
                    state_contract_text = f"<s>Ежемесячная выплата Штат/Контракт : {rate_sng_contract} RUB</s>"
                else:
                    acts_text = 'Актирование: ежемесячное\n'
                    state_contract_text = f"Ежемесячная выплата Штат/Контракт : {rate_sng_contract} RUB"
                if short_project or long_payment:
                    state_contract_text = f"<s>{state_contract_text}</s>"
                if only_fulltime:
                    ip_samoz_text = f"<s>ИП : {rate_sng_ip} RUB,\n Самозанятый : {rate_sng_samozanyatii} RUB</s>"
                else:
                    ip_samoz_text = f"ИП : {rate_sng_ip} RUB,\n Самозанятый : {rate_sng_samozanyatii} RUB"
                        
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до:\n{state_contract_text}\n{delay_payment_text}{acts_text}\n{ip_samoz_text}\n\n{text}"
            else:
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n\n{text}"
                print(text_cleaned)
        formatted_text = await format_vacancy_gemini(text_cleaned, vacancy_id=vac_id)
        print(formatted_text)
        print(formatted_text)
        if utochnenie == 'True' or utochnenie is True:
            await telethon_client.send_message(
                GROUP_ID,
                formatted_text,
            )
            return
                
        try:
            await message.answer(formatted_text, parse_mode='HTML')
        except Exception as e:
            await message.answer(f'Ошибка при отправке вакансии {e}')
            return
        await state.update_data(text_cleaned=formatted_text, vac_id=vac_id)
    except Exception as e:
        await message.answer(f'Ошибка при обработке вакансии {e}')
        return
    await message.answer('Выберите топик куда отправить вакансию', reply_markup=await send_kb())
    await state.set_state(ScanHand.waiting_for_topic)


@dp.callback_query(ScanHand.waiting_for_topic, F.data.startswith("topic:"))
async def scan_hand_topic(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    topic_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    text_cleaned = data.get('text_cleaned')
    vac_id = data.get('vac_id')
    if not text_cleaned:
        await callback.message.answer('Нет текста')
        return

    await telethon_client.send_message(entity = -1002658129391, message=text_cleaned, reply_to=topic_id, parse_mode='html')
    await state.clear()
    await callback.message.answer('Вакансия отправлена')
    await send_mess_to_group(GROUP_ID, text_cleaned, vac_id, bot)
    




# --- Запуск всех задач ---
async def main():
    await init_db()
    await telethon_client.start(phone=PHONE_NUMBER)
    await register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot)

    # Запускаем мониторинг зачёркнутых сообщений
    asyncio.create_task(monitor_and_cleanup(telethon_client, AsyncSessionLocal))
    asyncio.create_task(check_and_delete_duplicates(telethon_client, -1002658129391, bot, TOPIC_MAP))
    # Запускаем Telethon клиента
    asyncio.create_task(telethon_client.run_until_disconnected())
    asyncio.create_task(cleanup_by_striked_id(telethon_client, src_chat_id=-1002658129391, dst_chat_id=-1002189931727))
    asyncio.create_task(check_old_messages_and_mark(telethon_client, -1002658129391, bot))
    # Запускаем Aiogram бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
