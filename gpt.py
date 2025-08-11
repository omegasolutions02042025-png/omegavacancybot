#!/usr/bin/env python3

from __future__ import annotations

import os

from yandex_cloud_ml_sdk import YCloudML
from dotenv import load_dotenv

load_dotenv()

AUTH_TOKEN = os.getenv('AUTH_TOKEN')
FOLDER_ID = os.getenv('FOLDER_ID')


def del_contacts_gpt(text):
    messages = [
        {
            "role": "system",
            "text": "Ты — помощник, который удаляет из текста все контактные данные (номера телефонов, email, ссылки и т.п.) и возвращает только очищенный текст без комментариев.",
        },
        {
            "role": "user",
            "text": text,
        },
    ]

    sdk = YCloudML(
        folder_id=FOLDER_ID,
        auth= AUTH_TOKEN,
    )



    result = sdk.models.completions("yandexgpt").configure(temperature=0.5).run(messages)
    clean_text = result.alternatives[0].text
    print(clean_text)
    return clean_text


