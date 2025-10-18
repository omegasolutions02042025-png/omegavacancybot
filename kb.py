from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from db import get_tg_user, get_email_user

async def main_kb():
    builder = InlineKeyboardBuilder()
    #builder.button(text="Управление обязательными словами", callback_data='slova_info')
    
    #builder.button(text="Подключение канала", callback_data='channels_info')
    #builder.button(text='Сканировать каналы', callback_data='scan_channels')
    builder.button(text='Сканировать RedlabPartners 14 дней', callback_data='scan_redlab')
    builder.button(text='Сканировать RedlabPartners 21 день', callback_data='scan_redlab_21')
    builder.button(text='Сканировать RedlabPartners(1 день)', callback_data='scan_redlab_day')
    builder.button(text = 'Добавить вакансию вручную', callback_data='scan_hand')
    
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


async def send_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="DevOps", callback_data="topic:17")
    builder.button(text="Frontend", callback_data="topic:9")
    builder.button(text="Backend", callback_data="topic:4")
    builder.button(text="Аналитики", callback_data="topic:11")
    builder.button(text="Базы данных", callback_data="topic:13")
    builder.button(text="QA", callback_data="topic:6")
    builder.button(text="Дизайнеры", callback_data="topic:29")
    builder.button(text="Безопасность", callback_data="topic:23")
    builder.button(text="Лидеры", callback_data="topic:21")
    builder.button(text='Архитекторы', callback_data="topic:25")
    builder.button(text='1С', callback_data="topic:15")
    builder.button(text='Support', callback_data="topic:27")
    builder.button(text='Mobile', callback_data="topic:19")
    builder.button(text='General', callback_data="topic:1")
    builder.adjust(3)
    return builder.as_markup()


async def scan_vac_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Проверить кандидатов на соотвествие вакансии', callback_data='scan_kand_for_vac')
    builder.adjust(1)
    return builder.as_markup()

def scan_vac_rekr_yn_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Да', callback_data='yes_vac_rekr')
    builder.button(text='Нет', callback_data='no_vac_rekr')
    return builder.as_markup()

def utochnit_prichinu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Уточнить причину', callback_data='utochnit_prichinu')
    return builder.as_markup()

def generate_mail_kb(verdict_text: str):
    print(verdict_text)
    callback = None
    if verdict_text == 'Полностью подходит':
        callback = 'PP'
        builder = InlineKeyboardBuilder()
        builder.button(text='Сгенерировать письмо для кандидата', callback_data=f'generate_mail:{callback}')
        return builder.as_markup()
    elif verdict_text == 'Частично подходит (нужны уточнения)':
        callback = 'CP'
        builder = InlineKeyboardBuilder()
        builder.button(text='Сгенерировать уточняющее письмо', callback_data=f'generate_mail:{callback}')
        return builder.as_markup()
    elif verdict_text == 'Не подходит':
        callback = 'NP'
        builder = InlineKeyboardBuilder()
        builder.button(text='Сгенерировать отказ', callback_data=f'generate_mail:{callback}')
        return builder.as_markup()
    return None

def generate_klient_mail_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Сгенерировать письмо для клиента', callback_data='generate_klient_mail')
    return builder.as_markup()


def get_all_info_kb(verdict: str):
    builder = InlineKeyboardBuilder()
    if verdict == 'Полностью подходит':
        callback = 'PP'
    elif verdict == 'Частично подходит (нужны уточнения)':
        callback = 'CP'
    elif verdict == 'Не подходит':
        callback = 'NP'
    builder.button(text='Подробнее', callback_data=f'get_all_info:{callback}')
    return builder.as_markup()


def send_mail_to_candidate_kb(verdict: str):
    print(verdict)
    callback = None
    if verdict == 'Полностью подходит':
        callback = 'PP'
    elif verdict == 'Частично подходит (нужны уточнения)':
        callback = 'CP'
    elif verdict == 'Не подходит':
        callback = 'NP'
    builder = InlineKeyboardBuilder()
    builder.button(text='Отправить письмо кандидату', callback_data=f'send_mail_to_candidate:{callback}')
    return builder.as_markup()

def send_mail_or_generate_client_mail_kb():
    callback = 'PP'
    builder = InlineKeyboardBuilder()
    builder.button(text='Отправить письмо кандидату', callback_data=f'send_mail_to_candidate:{callback}')
    builder.button(text='Сгенерировать письмо для клиента', callback_data='generate_klient_mail')
    return builder.as_markup()


def create_contacts_kb(contacts: dict,verdict : str):
    """
    Создаёт inline-клавиатуру для доступных контактов кандидата.
    Пример входных данных:
    {
      "phone": "Нет (требуется уточнение)",
      "email": "example@gmail.com",
      "telegram": "@username",
      "linkedin": "https://linkedin.com/in/someone"
    }
    """
    builder = InlineKeyboardBuilder()


    # Email
    email = contacts.get("email")
    if email and email.lower() not in ["нет", "нет (требуется уточнение)"]:
        builder.button(text="📧 Email", callback_data=f"con:e:{email}:{verdict}")

    # Telegram
    telegram = contacts.get("telegram")
    if telegram and telegram.lower() not in ["нет", "нет (требуется уточнение)"]:
        builder.button(text="💬 Telegram", callback_data=f"con:t:{telegram}:{verdict}")

    # LinkedIn
    linkedin = contacts.get("linkedin")
    if linkedin and linkedin.lower() not in ["нет", "нет (требуется уточнение)"]:
        builder.button(text="🔗 LinkedIn", callback_data=f"con:l:{linkedin}:{verdict}")

    # Телефон (если нужно отображать)
    phone = contacts.get("phone")
    if phone and phone.lower() not in ["нет", "нет (требуется уточнение)"]:
        builder.button(text="📞 Телефон", callback_data=f"con:p:{phone}:{verdict}")

    builder.adjust(2)
    return builder.as_markup()



def back_to_mail_kand_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Назад', callback_data='back_to_mail_kand')
    return builder.as_markup()

def viber_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Отправить вiber', callback_data='viber', url = 'viber://chat?number=%2B4957777777')
    return builder.as_markup()

def add_another_resume_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Добавить еще резюме', callback_data='add_another_resume')
    return builder.as_markup()


async def service_kb(user_name_tg):
    builder = InlineKeyboardBuilder()
    tg_privyazka = await get_tg_user(user_name_tg)
    email_privyazka = await get_email_user(user_name_tg)
    if tg_privyazka:
        builder.button(text='Удалить привязку Telegram', callback_data='remove_tg')
    else:
        builder.button(text='Привязать Telegram', callback_data='telegram')
    if email_privyazka:
        builder.button(text='Удалить привязку Gmail', callback_data='remove_email')
    else:
        builder.button(text='Привязать Gmail', callback_data='gmail')
    builder.adjust(1)
    return builder.as_markup()

def next_email_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Далее', callback_data='next_email')
    return builder.as_markup()


def next_telegram_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Далее', callback_data='next_telegram')
    return builder.as_markup()

def accept_delete_tg_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Подтвердить', callback_data='accept_delete_tg')
    return builder.as_markup()


def accept_delete_email_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Подтвердить', callback_data='accept_delete_email')
    return builder.as_markup()
