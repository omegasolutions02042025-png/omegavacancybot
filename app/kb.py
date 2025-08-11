from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

async def main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Управление обязательными словами", callback_data='slova_info')
    builder.button(text='Управление фильтрами', callback_data='filters_info' )
    builder.button(text="Подключение канала", callback_data='channels_info')
    builder.adjust(1)
    return builder.as_markup()
    

async def channels_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Вывести список каналов", callback_data='all_channels')
    builder.button(text="+ Добавить канал", callback_data='add_channel')
    builder.button(text="Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


async def channel_kb(id):
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить канал", callback_data=f"delete_channel:{id}")
    builder.adjust(1)
    return builder.as_markup()


async def slova_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Вывести список слов", callback_data='all_slova')
    builder.button(text="+ Добавить слово", callback_data='add_slovo')
    builder.button(text="Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

async def slovo_kb(id):
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить слово", callback_data=f"delete_slovo:{id}")
    builder.adjust(1)
    return builder.as_markup()

async def back_to_slova_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад в меню", callback_data="back_to_slova_menu")
    return kb.as_markup()

async def back_to_channel_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад в меню", callback_data="back_to_channel_menu")
    return kb.as_markup()



async def filters_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Вывести список фильтров", callback_data='all_filters')
    builder.button(text="+ Добавить фильтр", callback_data='add_filter')
    builder.button(text="Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

async def filter_kb(id):
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить фильтр", callback_data=f"delete_filter:{id}")
    builder.adjust(1)
    return builder.as_markup()

async def back_to_filter_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад в меню", callback_data="back_to_filter_menu")
    return kb.as_markup()