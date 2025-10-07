import aiosmtplib
from email.message import EmailMessage
from typing import List, Optional
import imaplib
import email
from email import policy
from typing import List, Dict, Optional

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


import imaplib
import email
from email import policy
from typing import List, Dict

def fetch_last_emails(
    imap_user: str, 
    imap_pass: str, 
    mailbox: str = 'inbox', 
    limit: int = 10
) -> List[Dict[str, str]]:
    """
    Получает последние 'limit' писем из Gmail через IMAP.

    Возвращает список словарей: {'subject': str, 'from': str, 'body': str}
    """
    imap_host = 'imap.gmail.com'
    mail = imaplib.IMAP4_SSL(imap_host)
    mail.login(imap_user, imap_pass)
    mail.select(mailbox)

    status, data = mail.search(None, 'ALL')
    if status != 'OK':
        raise Exception("Ошибка поиска писем")

    mail_ids = data[0].split()
    emails = []

    for mail_id in mail_ids[-limit:]:
        status, data = mail.fetch(mail_id, '(RFC822)')
        if status != 'OK':
            continue

        msg = email.message_from_bytes(data[0][1], policy=policy.default)
        subject = msg['subject']
        from_ = msg['from']

        # Получаем текст письма
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_content()
                    break
        else:
            body = msg.get_content()

        emails.append({
            'subject': subject,
            'from': from_,
            'body': body
        })

    mail.logout()
    return emails


emails = fetch_last_emails('omegasolutions02042025@gmail.com', 'beoc taay ilbx vwvi', limit=5)

for e in emails:
    print("Subject:", e['subject'])
    print("From:", e['from'])
    print("Body:", e['body'])
    print("------")