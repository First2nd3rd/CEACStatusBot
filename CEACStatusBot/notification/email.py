import random
import time
from smtplib import SMTP_SSL
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from .handle import NotificationHandle
from .format import build_body, build_subject

SMTP_TIMEOUT = 30
SMTP_ATTEMPTS = 3  # retry transient network/proxy/wake hiccups before giving up


class EmailNotificationHandle(NotificationHandle):
    def __init__(self, fromEmail: str, toEmail: str, emailPassword: str, hostAddress: str = '') -> None:
        super().__init__()
        self.__fromEmail = fromEmail
        self.__toEmail = toEmail.split("|")
        self.__emailPassword = emailPassword
        self.__hostAddress = hostAddress or "smtp." + fromEmail.split("@")[1]
        if ':' in self.__hostAddress:
            addr, port = self.__hostAddress.split(':')
            self.__hostAddress = addr
            self.__hostPort = int(port)
        else:
            self.__hostPort = 465

    def send(self, result):
        mail_title = build_subject(result)
        mail_content = build_body(result)

        msg = MIMEMultipart()
        msg["Subject"] = Header(mail_title, 'utf-8')
        msg["From"] = self.__fromEmail
        msg['To'] = ";".join(self.__toEmail)
        msg.attach(MIMEText(mail_content, 'plain', 'utf-8'))

        # Retry a few times so a brief timeout (network/proxy/just-woke-from-sleep)
        # doesn't lose the email or fail the whole run.
        refused: dict = {}
        last_error: Exception | None = None
        for attempt in range(1, SMTP_ATTEMPTS + 1):
            try:
                with SMTP_SSL(self.__hostAddress, self.__hostPort, timeout=SMTP_TIMEOUT) as smtp:
                    smtp.login(self.__fromEmail, self.__emailPassword)
                    refused = smtp.sendmail(self.__fromEmail, self.__toEmail, msg.as_string())
                last_error = None
                break
            except Exception as e:  # noqa: BLE001 - transient; retry then re-raise
                last_error = e
                print(f"[email] send attempt {attempt}/{SMTP_ATTEMPTS} failed: {e}")
                if attempt < SMTP_ATTEMPTS:
                    time.sleep(random.uniform(3, 6))

        if last_error is not None:
            raise last_error

        if refused:
            print(f"[email] some recipients refused: {refused}")
            raise RuntimeError(f"Email partially undelivered: {refused}")
        print(f"[email] sent to {', '.join(self.__toEmail)}")
