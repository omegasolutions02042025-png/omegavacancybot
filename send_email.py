import aiosmtplib
from email.message import EmailMessage
from typing import List, Optional

import aiosmtplib
from email.message import EmailMessage
from typing import List, Optional

async def send_email_gmail(
    sender_email: str,
    app_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    html: bool = False,
    attachments: Optional[List[str]] = None
):
    msg = EmailMessage()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    if html:
        msg.add_alternative(body, subtype='html')
    else:
        msg.set_content(body)

    # Добавляем вложения
    if attachments:
        for file_path in attachments:
            with open(file_path, 'rb') as f:
                file_data = f.read()
                file_name = file_path.split('/')[-1]
                msg.add_attachment(
                    file_data,
                    maintype='application',
                    subtype='octet-stream',
                    filename=file_name
                )

    # Отправка письма через Gmail
    try:
        await aiosmtplib.send(
            msg,
            hostname='smtp.gmail.com',
            port=465,
            username=sender_email,
            password=app_password,
            use_tls=True
        )
        print(f"✅ Письмо отправлено на {recipient_email}")
    except Exception as e:
        print(f"❌ Ошибка при отправке письма: {e}")


import asyncio

async def main():
    await send_email_gmail(
        sender_email='omegasolutions02042025@gmail.com',
        app_password='beoc taay ilbx vwvi',  # обязательно App Password
        recipient_email='artursimoncik@gmail.com',
        subject='Тестовое письмо',
        body='Привет! Это HTML-письмо.',
        html=False,
        attachments=['resume.pdf']  # можно передавать список файлов
    )

asyncio.run(main())
