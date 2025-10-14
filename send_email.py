import aiosmtplib
from email.message import EmailMessage
from typing import List, Optional
import imaplib
import email
from email import policy
from typing import List, Dict, Optional

from typing import Optional, List
from email.message import EmailMessage
import mimetypes
import aiosmtplib

async def send_email_gmail(
    sender_email: str,
    app_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    html: bool = False,
    attachments: Optional[List[str]] = None
) -> bool:
    msg = EmailMessage()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    if html:
        msg.add_alternative(body, subtype='html')
    else:
        msg.set_content(body)

    # вложения с корректным MIME
    if attachments:
        for file_path in attachments:
            ctype, encoding = mimetypes.guess_type(file_path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            with open(file_path, 'rb') as f:
                msg.add_attachment(
                    f.read(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=file_path.split('/')[-1],
                )

    try:
        resp = await aiosmtplib.send(
            msg,
            hostname='smtp.gmail.com',
            port=465,
            username=sender_email,
            password=app_password,
            use_tls=True
        )
        code = getattr(resp, "code", None)
        return isinstance(code, int) and 200 <= code < 300  # True при 2xx (обычно 250)
    except Exception:
        return False





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


