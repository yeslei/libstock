"""Run with python -m app.workers.notifications [--watch --interval 30]."""
import argparse
import time

from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.mail import MailConfigurationError, create_mail_sender
from app.services.notification_dispatcher import NotificationDispatcher


def run(dispatcher, *, limit: int, watch: bool, interval: int, sleep=time.sleep):
    while True:
        result = dispatcher.dispatch_batch(limit=limit)
        print(f"Examinadas: {result['examined']}; enviadas: {result['sent']}; envio não confirmado: {result['unconfirmed']}", flush=True)
        if not watch:
            return
        sleep(interval)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Envia notificações de disponibilidade pendentes; sem reenvio automático.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 1000 or not 1 <= args.interval <= 60:
        parser.error("limit deve ser 1–1000 e interval deve ser 1–60 segundos")
    try:
        # Validate transport before querying or consuming the queue.
        sender = create_mail_sender(get_settings())
        from app.core.database import SessionLocal
        run(NotificationDispatcher(SessionLocal, sender), limit=args.limit, watch=args.watch, interval=args.interval)
    except MailConfigurationError as exc:
        print(str(exc))
        return 2
    except ValidationError:
        print("Configuração inválida do worker. Revise as variáveis de ambiente sem expor os seus valores.")
        return 2
    except SQLAlchemyError:
        print("Falha de persistência no worker. Verifique o banco e concilie os envios não confirmados.")
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
