"""SMTP transport. No domain rules, retries or logging of message contents."""
import smtplib
import ssl
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate

from app.core.config import Settings


class MailConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class OutgoingMail:
    notification_id: int
    recipient: str
    subject: str
    message: str


class SmtpMailSender:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.smtp_host or not settings.smtp_from_email:
            raise MailConfigurationError("Configure SMTP_HOST e SMTP_FROM_EMAIL antes de iniciar o worker.")
        if bool(settings.smtp_username) != bool(settings.smtp_password):
            raise MailConfigurationError("Configure SMTP_USERNAME e SMTP_PASSWORD juntos, ou deixe ambos vazios.")

    def send(self, mail: OutgoingMail) -> None:
        settings = self.settings
        message = EmailMessage()
        message["From"] = Address(addr_spec=str(settings.smtp_from_email))
        message["To"] = Address(addr_spec=mail.recipient)
        message["Subject"] = mail.subject
        message["Date"] = formatdate(usegmt=True)
        domain = str(settings.smtp_from_email).rsplit("@", 1)[1]
        message["Message-ID"] = f"<libstock-notification-{mail.notification_id}@{domain}>"
        message.set_content(mail.message)
        context = ssl.create_default_context()
        factory = smtplib.SMTP_SSL if settings.smtp_security == "ssl" else smtplib.SMTP
        options = {"timeout": settings.smtp_timeout_seconds}
        if settings.smtp_security == "ssl":
            options["context"] = context
        with factory(settings.smtp_host, settings.smtp_port, **options) as connection:
            if settings.smtp_security == "starttls":
                connection.starttls(context=context)
            if settings.smtp_username:
                connection.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            refused = connection.send_message(message, from_addr=str(settings.smtp_from_email), to_addrs=[mail.recipient])
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
