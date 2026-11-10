import json
from unittest.mock import Mock

import httpx
import pytest

from app.core.config import Settings
from app.core.mail import BrevoMailSender, MailConfigurationError, MailDeliveryError, OutgoingMail, create_mail_sender


def settings(**overrides):
    return Settings(**(dict(_env_file=None, mail_transport="brevo", brevo_api_key="fake-secret",
                           mail_from_email="library@example.org") | overrides))


def mail(**overrides):
    return OutgoingMail(**(dict(notification_id=1, recipient="client@example.org",
                               subject="Reserva disponível", message="Retire no balcão.") | overrides))


def test_https_payload_and_secret_header_use_fixed_endpoint_without_smtp():
    def handler(request):
        assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
        assert request.headers["api-key"] == "fake-secret"
        assert json.loads(request.content) == {
            "sender": {"email": "library@example.org", "name": "LibStock"},
            "to": [{"email": "client@example.org"}],
            "subject": "Reserva disponível", "textContent": "Retire no balcão.",
        }
        assert request.extensions["timeout"]["read"] == 10
        return httpx.Response(201, json={"messageId": "<provider-id>"})
    BrevoMailSender(settings(), transport=httpx.MockTransport(handler)).send(mail())
    assert "fake-secret" not in repr(settings())
    assert isinstance(create_mail_sender(settings()), BrevoMailSender)


@pytest.mark.parametrize("status", [400, 401, 402, 429, 500, 302])
def test_rejection_and_redirect_never_retry_or_expose_provider_body(status):
    attempts = []
    def handler(request):
        attempts.append(request)
        return httpx.Response(status, text="fake-secret client@example.org", headers={"location": "https://other.invalid"})
    with pytest.raises(MailDeliveryError) as error:
        BrevoMailSender(settings(), transport=httpx.MockTransport(handler)).send(mail())
    assert len(attempts) == 1
    assert "fake-secret" not in str(error.value) and "client@example.org" not in str(error.value)


@pytest.mark.parametrize("body", [b"invalid json", b"{}", b'{"messageId":null}', b'[]'])
def test_ambiguous_success_is_not_fabricated(body):
    with pytest.raises(MailDeliveryError):
        BrevoMailSender(settings(), transport=httpx.MockTransport(
            lambda _: httpx.Response(201, content=body))).send(mail())


def test_timeout_is_sanitized_and_attempted_once():
    attempts = []
    def handler(request):
        attempts.append(request)
        raise httpx.ReadTimeout("fake-secret recipient data", request=request)
    with pytest.raises(MailDeliveryError) as error:
        BrevoMailSender(settings(), transport=httpx.MockTransport(handler)).send(mail())
    assert len(attempts) == 1 and "fake-secret" not in str(error.value)


@pytest.mark.parametrize("overrides", [{"recipient": "not-an-email"},
    {"recipient": "client@example.org\r\nBcc: other@example.org"}, {"subject": "Title\nBcc: other@example.org"}])
def test_invalid_legacy_input_is_rejected_before_network(overrides):
    handler = Mock()
    with pytest.raises(ValueError):
        BrevoMailSender(settings(), transport=httpx.MockTransport(handler)).send(mail(**overrides))
    handler.assert_not_called()


@pytest.mark.parametrize("overrides", [{"brevo_api_key": None}, {"brevo_api_key": " "}, {"mail_from_email": None}])
def test_missing_configuration_does_not_claim_queue(overrides):
    with pytest.raises(MailConfigurationError):
        create_mail_sender(settings(**overrides))
