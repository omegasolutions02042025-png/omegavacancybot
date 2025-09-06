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
from kb import main_kb, channels_kb, channel_kb, back_to_channel_menu_kb, send_kb
from teleton_client import get_channel_info, leave_channel_listening
from telethon_bot import (
    cleanup_by_striked_id, forward_recent_posts, register_handler, list_all_dialogs, monitor_and_cleanup, forward_messages_from_topics,register_topic_listener, check_and_delete_duplicates, has_strikethrough
)
from funcs import update_channels_and_restart_handler
import os
from dotenv import load_dotenv
from funcs import *
from gpt import process_vacancy
from googlesheets import find_rate_in_sheet_gspread, search_and_extract_values
import math
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

async def register_handler_wrapper():
    global current_handler
    if current_handler:
        telethon_client.remove_event_handler(current_handler)
        print("❌ Старый обработчик удалён")
    
    current_handler = await register_handler(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal, bot)
    print(f"✅ Новый обработчик событий зарегистрирован для {len(CHANNELS)} каналов")
CHANNELS = []  # Текущий список каналов для слежения

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
    print('start')
    if message.from_user.id not in [6264939461, 429765805]:
        return
    await message.answer(text="Основное меню", reply_markup = await main_kb())


@dp.callback_query(F.data == "channels_info")
async def get_filters_info(callback: CallbackQuery):
    await callback.message.edit_text(text='Управление каналами', reply_markup = await channels_kb())


@dp.callback_query(F.data == "add_channel")
async def add_channel_fsm(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text='Введите ID (число) канала')
    await state.set_state(AddChannel.waiting_for_id)

@dp.message(AddChannel.waiting_for_id)
async def add_channel_to_db(message: types.Message, state: FSMContext):
    text = str(message.text)
    if text.startswith('-') and text[1:].isdigit():
        channel_id = int(message.text)
        channel_username = await get_channel_info(channel_id_or_name=channel_id, phone_number=PHONE_NUMBER, client=telethon_client)
        if channel_username == False:
            await message.answer("Канал не найден")
            return
        channel_id = str(channel_id)

    elif text.startswith("@"):
        channel_username = message.text
        channel_id = await get_channel_info(channel_id_or_name=channel_username, phone_number=PHONE_NUMBER, client=telethon_client)
        if channel_id == False:
            await message.answer("Канал не найден")
            return
        channel_id = str(channel_id)
    else:
        await message.answer("Неверный формат! Введите ID (число) или @username канала.")
        return

    await state.set_state(AddChannel.waiting_for_name)
    await message.answer("Введите название канала")
    await state.update_data(channel_id=channel_id)


@dp.message(AddChannel.waiting_for_name)
async def add_channel_to_db(message: types.Message, state: FSMContext):
    channel_name = message.text
    channel_id = await state.get_data()
    channel_id = channel_id.get('channel_id')
    if channel_id == None:
        await message.answer("Не удалось добавить канал")
        return
    result = await add_channel(channel_id=channel_id, channel_name=channel_name)
    if result:
        await message.answer(text=f"{result}")
    else:
        await message.answer(text='Канал добавлен')
        channels = await get_all_channels()
        channel_ids = []
        for channel in channels:
            channel_ids.append(channel.channel_id)
        await update_channels_and_restart_handler(channel_ids, CHANNELS, register_handler_wrapper)
    await state.clear()


    await message.answer(text='Укправление каналами', reply_markup = await channels_kb())
    await state.clear()


@dp.callback_query(F.data == "all_channels")
async def get_all_channels_from_db(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    message_ids = []
    channels = await get_all_channels()
    for channel in channels:
        a = await callback.message.answer(
            text=f'Название канала: {channel.channel_name} \nID канала: {channel.channel_id}',
            reply_markup= await channel_kb(id=channel.channel_id))
        message_ids.append(a.message_id)
    await callback.message.answer("Нажмите чтобы вернутся в меню", reply_markup=await back_to_channel_menu_kb())
    await state.update_data(message_ids=message_ids)


@dp.callback_query(F.data.startswith("delete_channel"))
async def get_filters_info(callback: CallbackQuery):
    channel_id = int(callback.data.split(":")[1])
    await remove_channel(channel_id)
    await leave_channel_listening(channel_id=channel_id, phone_number=PHONE_NUMBER, client=telethon_client)
    await callback.message.delete()
    CHANNELS.remove(channel_id)
    await update_channels_and_restart_handler(CHANNELS, CHANNELS, register_handler_wrapper)


@dp.callback_query(F.data == 'back_to_channel_menu')
async def back_to_сhannel_menu(callback: CallbackQuery, state: FSMContext, bot : Bot):
    await callback.message.delete()
    ids = await state.get_data()
    ids = ids.get('message_ids')
    try:
        for id in ids:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=id)
        await callback.message.answer("Управление каналами", reply_markup=await channels_kb())
    except:
        await callback.message.answer("Управление каналами", reply_markup=await channels_kb())
    await state.clear()


@dp.callback_query(F.data == 'scan_channels')
async def scan_channels(calback : CallbackQuery):
    await calback.message.answer('Начинаю сканирование...')
    await forward_recent_posts(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal, bot)


@dp.callback_query(F.data == 'scan_redlab')
async def scan_redlab(calback : CallbackQuery):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=14, bot = bot)

@dp.callback_query(F.data == 'scan_redlab_day')
async def scan_redlab(calback : CallbackQuery):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=1, bot = bot)





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

    if oplata_filter(text):
        await message.answer('Оплата не подходит')
        return

    if check_project_duration(text):
        await message.answer('Маленькая продолжительность проекта')
        
        return

    try:
        text_gpt = await process_vacancy(text)
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
        print(vac_id)
        print(type(vac_id))
        rate = text_gpt.get("rate")
        vacancy = text_gpt.get('vacancy_title')
        deadline_date = text_gpt.get("deadline_date")
        deadline_time = text_gpt.get("deadline_time")
        utochnenie = text_gpt.get("utochnenie")
        if vacancy is None or vacancy == 'None':
            await message.answer('Вакансия отсеяна')
            return
        

        # Вакансия отсекается, если нет ID
        if vac_id is None  or vac_id == 'None':
            await message.answer('Вакансия отсеяна, нет ID')
            return

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
            return
                
        try:
            await message.answer(text_cleaned)
        except Exception as e:
            await message.answer(f'Ошибка при отправке вакансии {e}')
            return
        await state.update_data(text_cleaned=text_cleaned)
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
    if not text_cleaned:
        await callback.message.answer('Нет текста')
        return

    await telethon_client.send_message(entity = -1002658129391, message=text_cleaned, reply_to=topic_id)
    await state.clear()
    await callback.message.answer('Вакансия отправлена')
    




























# --- Функция обновления списка каналов ---





# --- Запуск всех задач ---
async def main():
    await init_db()
    await telethon_client.start(phone=PHONE_NUMBER)
    await list_all_dialogs(telethon_client, PHONE_NUMBER)
    channels = await get_all_channels()
    channels = [channel.channel_id for channel in channels]
    print(channels)
    await update_channels_and_restart_handler(channels, CHANNELS, register_handler_wrapper)
    await register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot)

    # Запускаем мониторинг зачёркнутых сообщений
    asyncio.create_task(monitor_and_cleanup(telethon_client, AsyncSessionLocal))
    asyncio.create_task(check_and_delete_duplicates(telethon_client, -1002658129391, bot, TOPIC_MAP))
    # Запускаем Telethon клиента
    asyncio.create_task(telethon_client.run_until_disconnected())
    asyncio.create_task(cleanup_by_striked_id(telethon_client, src_chat_id=-1002658129391, dst_chat_id=-1002189931727))
    # Запускаем Aiogram бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
