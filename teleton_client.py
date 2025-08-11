import inspect
import functools
from collections import namedtuple
from telethon.errors import UserAlreadyParticipantError

ArgSpec = namedtuple('ArgSpec', ['args', 'varargs', 'keywords', 'defaults'])

def getargspec(func):
    """Legacy wrapper for inspect.getfullargspec()."""
    spec = inspect.getfullargspec(func)
    return ArgSpec(
        args=spec.args,
        varargs=spec.varargs,
        keywords=spec.varkw,
        defaults=spec.defaults,
    )

inspect.getargspec = getargspec

import db
from telethon import TelegramClient
from itertools import product
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.types import PeerChannel
import pymorphy2
from telethon.errors import UsernameInvalidError, ChannelInvalidError

async def get_channel_info(channel_id_or_name, client, phone_number):
    await client.start(phone=phone_number)
    channel_id_or_name = str(channel_id_or_name)
    if channel_id_or_name.startswith("@"):
        try:
            channel = channel_id_or_name[1:]
            channel = await client.get_entity((channel_id_or_name))
            await client(JoinChannelRequest(channel))
            channel_id = f"-100{channel.id}"
            return channel_id
        
        except UserAlreadyParticipantError:
            print(f"ℹ️ Уже подписан на канал: {entity.title}")
        except Exception as e:
            print(f"❌ Ошибка при подписке: {e}")
    else:
        try:
            channel_id_or_name = int(channel_id_or_name)
            channel = await client.get_entity(PeerChannel(channel_id_or_name))
            await client(JoinChannelRequest(channel))
            channel_username = f'@{channel.username}'
            return channel_username
        except UserAlreadyParticipantError:
            print(f"ℹ️ Уже подписан на канал: {entity.title}")
        except Exception as e:
            print(f"❌ Ошибка при подписке: {e}")

async def leave_channel_listening(channel_id, client, phone_number):
    await client.start(phone=phone_number)
    
    channel_id = int(channel_id)
    try:
        channel = await client.get_entity(PeerChannel(channel_id))
        await client(LeaveChannelRequest(channel))
    except Exception as e:
        print(f"❌ Ошибка при выходе: {e}")
        
 

async def generate_all_case_forms(phrase):
    morph = pymorphy2.MorphAnalyzer()

    """Генерирует все возможные падежные формы фразы"""
    words = phrase.split()
    if not words:
        return []
    
    # Получаем все возможные варианты склонения для каждого слова
    word_variants = []
    for word in words:
        parsed = morph.parse(word)[0]  # берем первый вариант разбора
        if parsed.tag.POS in {'NOUN', 'ADJF', 'ADJS', 'PRTF', 'PRTS', 'NUMR'}:
            cases = ['nomn', 'gent', 'datv', 'accs', 'ablt', 'loct']
            variants = []
            for case in cases:
                try:
                    inflected = parsed.inflect({case})
                    if inflected:
                        variants.append(inflected.word)
                except:
                    continue
            word_variants.append(variants if variants else [word])
        else:
            word_variants.append([word])  # для неизменяемых слов
    
    # Генерируем все возможные комбинации слов в разных падежах
    all_forms = []
    for combination in product(*word_variants):
        all_forms.append(' '.join(combination))
    
    return list(set(all_forms))  # убираем дубли



import html
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityMentionName, MessageEntityUrl
)

async def message_to_html_safe(message):
    text = message.message or "" 
   
    entities = message.entities or []

    if not entities:
        return html.escape(text)

    # Создаем список символов
    text_chars = list(text)
    insertions = []

    # Собираем все вставки тегов
    for entity in entities:
        offset = entity.offset
        length = entity.length
        end = offset + length

        if isinstance(entity, MessageEntityBold):
            insertions.append((offset, "<b>"))
            insertions.append((end, "</b>"))
        elif isinstance(entity, MessageEntityItalic):
            insertions.append((offset, "<i>"))
            insertions.append((end, "</i>"))
        elif isinstance(entity, MessageEntityUnderline):
            insertions.append((offset, "<u>"))
            insertions.append((end, "</u>"))
        elif isinstance(entity, MessageEntityStrike):
            insertions.append((offset, "<s>"))
            insertions.append((end, "</s>"))
        elif isinstance(entity, MessageEntityCode):
            insertions.append((offset, "<code>"))
            insertions.append((end, "</code>"))
        elif isinstance(entity, MessageEntityPre):
            insertions.append((offset, "<pre>"))
            insertions.append((end, "</pre>"))
        elif isinstance(entity, MessageEntityTextUrl):
            url = html.escape(entity.url)
            insertions.append((offset, f'<a href="{url}">'))
            insertions.append((end, "</a>"))
        elif isinstance(entity, MessageEntityUrl):
            url_text = html.escape(text[offset:end])
            insertions.append((offset, f'<a href="{url_text}">'))
            insertions.append((end, "</a>"))
        elif isinstance(entity, MessageEntityMentionName):
            user_id = entity.user_id
            insertions.append((offset, f'<a href="tg://user?id={user_id}">'))
            insertions.append((end, "</a>"))

    # Сортируем вставки по позиции, но закрывающие теги вставляем первыми
    insertions.sort(key=lambda x: (x[0], 0 if "/" in x[1] else 1), reverse=True)

    for index, tag in insertions:
        text_chars.insert(index, tag)

    return html.escape("".join(text_chars), quote=False).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

