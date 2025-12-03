from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from db import get_tg_user, get_email_user, get_contact
from aiogram.types import CopyTextButton

async def main_kb():
    builder = InlineKeyboardBuilder()
    #builder.button(text="Управление обязательными словами", callback_data='slova_info')
    
    #builder.button(text="Подключение канала", callback_data='channels_info')
    #builder.button(text='Сканировать каналы', callback_data='scan_channels')
    builder.button(text='Сканировать RedlabPartners 14 дней', callback_data='scan_redlab')
    builder.button(text='Сканировать RedlabPartners 21 день', callback_data='scan_redlab_21')
    builder.button(text='Сканировать RedlabPartners(1 день)', callback_data='scan_redlab_day')
    builder.button(text = 'Добавить вакансию вручную', callback_data='scan_hand')
    builder.button(text="Отправить вакансии на сайт(Не НАЖИМАТЬ!)", callback_data="send_vac_to_site")
    
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

def generate_mail_kb(again = False):
    
    builder = InlineKeyboardBuilder()
   
       
    builder.button(text='Сгенерировать письмо финалиста', callback_data=f'generate_mail:PP')
    builder.button(text='Сгенерировать уточняющее письмо', callback_data=f'generate_mail:CP')
    builder.button(text='Сгенерировать отказ', callback_data=f'generate_mail:NP')
    builder.button(text='Сгенерировать письмо для клиента', callback_data=f'generate_klient_mail')
    builder.button(text='Назад к письму', callback_data='back_to_mail')

    if not again:
        builder.button(text='Свернуть', callback_data=f'hide')
    builder.adjust(1)
    return builder.as_markup()
    

def generate_klient_mail_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Сгенерировать письмо для клиента', callback_data='generate_klient_mail')
    return builder.as_markup()


def get_all_info_kb():  
    builder = InlineKeyboardBuilder()
    
    builder.button(text='Подробнее', callback_data=f'get_all_info')
    builder.button(text='Удалить кандидата из списка', callback_data=f'del')
    builder.adjust(1)
    return builder.as_markup()


def send_mail_to_candidate_kb(verdict: str, mail: str):
   
    builder = InlineKeyboardBuilder()
    
    
    if verdict == 'Частично подходит (нужны уточнения)':
        builder.button(text='Добавить уточнения и сделать WL', callback_data='add_utochnenie')
    elif verdict == 'Полностью подходит':
        builder.button(text='Вернуться к письму для клиента', callback_data='back_to_group')
        
    
    builder.button(text='Отправить письмо кандидату', callback_data=f'send_mail_to_candidate')
    builder.button(text='Показать сверку', callback_data=f'show_sverka')
    builder.button(text='Копировать', switch_inline_query_current_chat=f'{mail}')
    builder.button(text='Удалить кандидата из списка', callback_data=f'del')
    builder.button(text='Сгенерировать письмо снова', callback_data='generate_mail_again')
    builder.adjust(1)
    return builder.as_markup()

def send_mail_or_generate_client_mail_kb(mail: str, candidate_mail: str = None):
    builder = InlineKeyboardBuilder()
    builder.button(text='Отправить письмо кандидату', callback_data=f'send_mail_to_candidate')
    if candidate_mail:
        builder.button(text = 'Вернутся к письму для кандидата', callback_data='back_to_group')
    builder.button(text='Сгенерировать письмо для клиента', callback_data='generate_klient_mail')
    builder.button(text='Показать сверку', callback_data='show_sverka')
    builder.button(text='Копировать', switch_inline_query_current_chat=f'{mail}')
    builder.button(text='Удалить кандидата из списка', callback_data='del')
    builder.button(text='Сгенерировать письмо снова', callback_data='generate_mail_again')
    builder.adjust(1)
    return builder.as_markup()


async def create_contacts_kb(message_id):
  
    print(message_id)
    builder = InlineKeyboardBuilder()
    contacts = await get_contact(message_id)
    
    telegram = None
    email = None
    phone = None
    
    if contacts:
        telegram = contacts.contact_tg
        email = contacts.contact_email
        phone = contacts.contact_phone
    
    
    if not phone and not telegram and not email:
            builder.button(text="Добавить контакты", callback_data="add_contacts")
            return builder.as_markup()
    if telegram:
        builder.button(text="💬 Telegram", callback_data=f"con:t:{telegram}")
    if email:
        builder.button(text="📧 Email", callback_data=f"con:e:{email}")
    if phone:
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        builder.button(text=f"📞 {phone}", callback_data=f"con:p:{phone}")
        
    builder.button(text="Добавить контакты", callback_data="add_contacts")
    builder.button(text="Назад к письму", callback_data="show_mail")
    builder.adjust(2,1,1)
    return builder.as_markup()

def back_to_contact_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="back_to_contact")
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

def link_to_thread_kb(link):
    builder = InlineKeyboardBuilder()
    builder.button(text='Перейти к треду', callback_data='link_to_thread', url=link)
    return builder.as_markup()


def show_mail_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Показать письмо', callback_data='show_mail')
    builder.button(text='Удалить кандидата из списка', callback_data='del')
    builder.adjust(1)
    return builder.as_markup()

def send_to_group_kb(mail):
    builder = InlineKeyboardBuilder()
    #builder.button(text='Отправить в группу письмо и WL резюме', callback_data='send_to_group')
    #builder.button(text='Отправить в группу только письмо', callback_data='send_to_group_mail')
    builder.button(text='Скачать WL резюме', callback_data='show_wl')
    builder.button(text='Копировать', switch_inline_query_current_chat=f'{mail}')
    builder.button(text='Назад к письму', callback_data='back_to_mail')
    builder.button(text='Удалить кандидата из списка', callback_data='del')
    builder.adjust(1)
    return builder.as_markup()


def contacts_add_kb(chat_id, mess_id):
    builder = InlineKeyboardBuilder()
    builder.button(text='Telegram', callback_data='addcontacts_tg')
    builder.button(text='Email', callback_data='addcontacts_email')
    builder.button(text='Телефон', callback_data='addcontacts_phone')
    builder.button(text='Назад', url=f'https://t.me/c/{chat_id}/{mess_id}')
    return builder.as_markup()

def add_con_url_kb(chat_id):
    builder = InlineKeyboardBuilder()
    builder.button(text='Перейти', url=f'https://t.me/c/{chat_id}/1')
    builder.button(text="Назад", callback_data="back_to_contact")
    return builder.as_markup()

def return_to_contact_kb(mess_id,chat_id):
    builder = InlineKeyboardBuilder()
    
    builder.button(text='Вернуться к кандидату', url=f'https://t.me/c/{chat_id}/{mess_id}')
    return builder.as_markup()


def for_basa_or_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Загрузить из базы', callback_data='for_basa')
    builder.button(text='Загрузить вручную', callback_data='for_main')
    builder.adjust(1)
    return builder.as_markup()

def start_sverka_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='Начать сверку', callback_data='start_sverka')
    return builder.as_markup()



def add_utochnenie_url_kb(chat_id, mess_id):
    chat_id = str(chat_id)
    chat_id = chat_id.replace("-100", "")
    builder = InlineKeyboardBuilder()
    builder.button(text='Перейти', url=f'https://t.me/c/{chat_id}/{mess_id}')
    builder.button(text="Назад", callback_data="back_to_utochnenie")
    return builder.as_markup()

def add_ut_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить уточнения", callback_data="add_ut")
    return builder.as_markup()


def back_to_ut_url_kb(mess_id, chat_id):
    chat_id = str(chat_id)
    chat_id = chat_id.replace("-100", "")
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", url=f'https://t.me/c/{chat_id}/{mess_id}')
    return builder.as_markup()


