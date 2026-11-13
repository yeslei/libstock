"""Optional queue delivery inside the existing API, while its process is awake."""
import asyncio
from contextlib import asynccontextmanager
import logging

from app.core.config import get_settings
from app.core.mail import MailConfigurationError, create_mail_sender
from app.services.notification_dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


def build_dispatcher(settings):
    # Configuration is checked before a session is opened or any message is claimed.
    sender = create_mail_sender(settings)
    from app.core.database import SessionLocal
    return NotificationDispatcher(SessionLocal, sender)


async def run_delivery(dispatcher, stop: asyncio.Event, interval: int):
    while not stop.is_set():
        try:
            # Synchronous DB and transport run outside the HTTP event loop.
            # One message per iteration bounds work during shutdown and free-tier load.
            result = await asyncio.to_thread(dispatcher.dispatch_batch, limit=1)
            if result["examined"]:
                logger.info("Notificações: examinadas=%s enviadas=%s não_confirmadas=%s",
                            result["examined"], result["sent"], result["unconfirmed"])
        except Exception:
            # Do not log database URLs, provider payloads, recipients or credentials.
            logger.warning("Falha no processamento de notificações; consulte a fila e o provedor.")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass


@asynccontextmanager
async def notification_lifespan(_app):
    settings = get_settings()
    if not settings.notification_delivery_in_api:
        yield
        return
    try:
        dispatcher = build_dispatcher(settings)
    except MailConfigurationError:
        logger.warning("Envio de notificações não configurado; mensagens permanecem na fila.")
        yield
        return
    stop = asyncio.Event()
    task = asyncio.create_task(run_delivery(dispatcher, stop, settings.notification_delivery_interval_seconds))
    try:
        yield
    finally:
        # Finish the current attempt rather than cancel a thread after an external effect.
        stop.set()
        await task
