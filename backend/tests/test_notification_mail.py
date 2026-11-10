from unittest.mock import MagicMock, Mock, patch

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.mail import MailConfigurationError, OutgoingMail, SmtpMailSender
from app.workers.notifications import main, run


def settings(**changes):
    values = dict(_env_file=None, smtp_host="smtp.example.org", smtp_from_email="library@example.org",
        smtp_username="library", smtp_password="test-password", smtp_security="starttls")
    return Settings(**(values | changes))


def test_missing_transport_configuration_is_rejected_and_secrets_are_masked():
    with pytest.raises(MailConfigurationError):
        SmtpMailSender(settings(smtp_host=None))
    with pytest.raises(MailConfigurationError):
        SmtpMailSender(settings(smtp_from_email=None))
    with pytest.raises(MailConfigurationError):
        SmtpMailSender(settings(smtp_password=None))
    assert isinstance(settings().smtp_password, SecretStr)
    assert "test-password" not in repr(settings())


@pytest.mark.parametrize("security,factory", [("starttls", "SMTP"), ("ssl", "SMTP_SSL")])
def test_smtp_uses_tls_timeout_current_address_and_stable_message_id(security, factory):
    sender = SmtpMailSender(settings(smtp_security=security))
    connection = MagicMock()
    connection.send_message.return_value = {}
    with patch(f"app.core.mail.smtplib.{factory}") as smtp:
        smtp.return_value.__enter__.return_value = connection
        sender.send(OutgoingMail(12, "client@example.org", "Sua reserva", "Retire no balcão."))
    assert smtp.call_args.kwargs["timeout"] == 10
    if security == "starttls":
        connection.starttls.assert_called_once()
        methods = [call[0] for call in connection.method_calls]
        assert methods.index("starttls") < methods.index("login") < methods.index("send_message")
    else:
        assert smtp.call_args.kwargs["context"].check_hostname
    connection.login.assert_called_once_with("library", "test-password")
    message = connection.send_message.call_args.args[0]
    assert message["Message-ID"] == "<libstock-notification-12@example.org>"
    assert connection.send_message.call_args.kwargs["to_addrs"] == ["client@example.org"]
    assert "Retire no balcão." in message.get_content()


@pytest.mark.parametrize("recipient,subject", [("client@example.org\r\nBcc: other@example.org", "Reserva"),
    ("client@example.org", "Reserva\nBcc: other@example.org")])
def test_header_injection_is_rejected_before_connecting(recipient, subject):
    with patch("app.core.mail.smtplib.SMTP") as smtp:
        with pytest.raises(ValueError):
            SmtpMailSender(settings()).send(OutgoingMail(1, recipient, subject, "Conteúdo"))
        smtp.assert_not_called()


@pytest.mark.parametrize("values", [{"smtp_timeout_seconds": 0}, {"smtp_timeout_seconds": 61},
    {"smtp_security": "none"}, {"smtp_port": 0}, {"smtp_from_email": "invalid"}])
def test_smtp_settings_validate_bounded_secure_configuration(values):
    with pytest.raises(ValidationError):
        settings(**values)


def test_worker_configuration_failure_does_not_dispatch(capsys):
    with patch("app.workers.notifications.get_settings", return_value=settings(smtp_host=None)), \
         patch("app.workers.notifications.NotificationDispatcher") as dispatcher:
        assert main([]) == 2
        dispatcher.assert_not_called()
    assert "SMTP_HOST" in capsys.readouterr().out


def test_invalid_environment_never_prints_validation_input_or_secret(capsys):
    def invalid_settings():
        return settings(jwt_secret_key="private-value")
    with patch("app.workers.notifications.get_settings", side_effect=invalid_settings), \
         patch("app.workers.notifications.NotificationDispatcher") as dispatcher:
        assert main([]) == 2
        dispatcher.assert_not_called()
    captured = capsys.readouterr()
    assert "Configuração inválida" in captured.out
    assert "private-value" not in captured.out + captured.err


def test_watch_is_bounded_and_stops_on_interrupt():
    dispatcher = Mock()
    dispatcher.dispatch_batch.return_value = {"examined": 1, "sent": 1, "unconfirmed": 0}
    sleep = Mock(side_effect=KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        run(dispatcher, limit=10, watch=True, interval=30, sleep=sleep)
    dispatcher.dispatch_batch.assert_called_once_with(limit=10)
    sleep.assert_called_once_with(30)


@pytest.mark.parametrize("args", [["--limit", "0"], ["--interval", "61"]])
def test_worker_rejects_invalid_limits(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
