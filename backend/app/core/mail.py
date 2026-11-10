"""SMTP and HTTPS transports without domain rules, retries or content logging."""
import smtplib
import ssl
import httpx
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate

from app.core.config import Settings


class MailConfigurationError(ValueError):
    pass


class MailDeliveryError(Exception):
    """Sanitized delivery failure; never includes request, response or credentials."""


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


class BrevoMailSender:
    """HTTPS transport usable on Render Free; no paid SDK or SMTP port needed."""

    ENDPOINT = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None):
        if not settings.brevo_api_key or not settings.brevo_api_key.get_secret_value().strip() or not settings.mail_from_email:
            raise MailConfigurationError("Configure BREVO_API_KEY e MAIL_FROM_EMAIL para o envio por HTTPS.")
        self.settings = settings
        self.transport = transport

    def send(self, mail: OutgoingMail) -> None:
        # Validate persisted legacy addresses and reject header injection before networking.
        recipient = Address(addr_spec=mail.recipient)
        if not recipient.username or not recipient.domain:
            raise ValueError("Destinatário inválido.")
        headers_check = EmailMessage()
        headers_check["Subject"] = mail.subject
        payload = {
            "sender": {"email": str(self.settings.mail_from_email), "name": "LibStock"},
            "to": [{"email": recipient.addr_spec}],
            "subject": mail.subject,
            "textContent": mail.message,
        }
        try:
            with httpx.Client(timeout=self.settings.mail_timeout_seconds,
                              follow_redirects=False, transport=self.transport) as client:
                response = client.post(self.ENDPOINT, json=payload, headers={
                    "api-key": self.settings.brevo_api_key.get_secret_value(),
                    "accept": "application/json",
                })
                if response.status_code != 201:
                    raise MailDeliveryError("O provedor não confirmou o envio.")
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("messageId"), str) or not data["messageId"]:
                    raise MailDeliveryError("O provedor não confirmou o envio.")
        except (httpx.HTTPError, ValueError):
            raise MailDeliveryError("O provedor não confirmou o envio.") from None


def create_mail_sender(settings: Settings):
    return BrevoMailSender(settings) if settings.mail_transport == "brevo" else SmtpMailSender(settings)
