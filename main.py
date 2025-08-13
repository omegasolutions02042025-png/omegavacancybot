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
from kb import main_kb, channels_kb, channel_kb, back_to_channel_menu_kb
from teleton_client import get_channel_info, leave_channel_listening, forward_messages_from_topics
from telethon_bot import (
    forward_recent_posts, register_handler, list_all_dialogs, monitor_and_cleanup
)
from funcs import update_channels_and_restart_handler
import os
from dotenv import load_dotenv


load_dotenv()

# Вставь свои данные
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
GROUP_ID = os.getenv("GROUP_ID")
current_handler = None  # Храним текущий обработчик

async def register_handler_wrapper():
    global current_handler
    if current_handler:
        telethon_client.remove_event_handler(current_handler)
        print("❌ Старый обработчик удалён")
    
    current_handler = await register_handler(telethon_client, CHANNELS, GROUP_ID, AsyncSessionLocal)
    print(f"✅ Новый обработчик событий зарегистрирован для {len(CHANNELS)} каналов")
CHANNELS = []  # Текущий список каналов для слежения

# --- Telethon клиент ---
telethon_client = TelegramClient('session_name', API_ID, API_HASH)

# --- Aiogram бот ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- FSM States ---
class AddChannel(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()


TOPIC_MAP = {
    (-1002189931727, 3): (-1002658129391, 4),
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
    await forward_recent_posts(telethon_client, CHANNELS, GROUP_ID)


@dp.callback_query(F.data == 'scan_redlab')
async def scan_redlab(calback : CallbackQuery):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP)





@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(text="Основное меню", reply_markup = await main_kb())






































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

    # Запускаем мониторинг зачёркнутых сообщений
    asyncio.create_task(monitor_and_cleanup(telethon_client, AsyncSessionLocal))

    # Запускаем Telethon клиента
    asyncio.create_task(telethon_client.run_until_disconnected())

    # Запускаем Aiogram бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
