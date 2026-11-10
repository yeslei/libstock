import asyncio
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.mail import MailConfigurationError
from app.services import notification_lifecycle as lifecycle


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("enabled", [False, True])
async def test_disabled_or_missing_config_preserves_queue_and_api_starts(monkeypatch, enabled, caplog):
    monkeypatch.setattr(lifecycle, "get_settings", lambda: SimpleNamespace(notification_delivery_in_api=enabled))
    build = Mock(side_effect=MailConfigurationError("private-key"))
    monkeypatch.setattr(lifecycle, "build_dispatcher", build)
    async with lifecycle.notification_lifespan(None):
        pass
    assert build.call_count == int(enabled)
    assert "private-key" not in caplog.text


@pytest.mark.anyio
async def test_api_loop_runs_off_event_loop_and_finishes_attempt_on_shutdown(monkeypatch):
    started, release, finished = Event(), Event(), Event()
    def dispatch(*, limit):
        assert limit == 1
        started.set()
        assert release.wait(timeout=3)
        finished.set()
        return {"examined": 1, "sent": 1, "unconfirmed": 0}
    dispatcher = SimpleNamespace(dispatch_batch=Mock(side_effect=dispatch))
    monkeypatch.setattr(lifecycle, "get_settings", lambda: SimpleNamespace(
        notification_delivery_in_api=True, notification_delivery_interval_seconds=30))
    monkeypatch.setattr(lifecycle, "build_dispatcher", lambda _: dispatcher)
    async with lifecycle.notification_lifespan(None):
        assert await asyncio.to_thread(started.wait, 3)
        # The loop remains responsive while the transport is blocked in another thread.
        await asyncio.sleep(0)
        release.set()
    assert finished.is_set()
    dispatcher.dispatch_batch.assert_called_once_with(limit=1)


@pytest.mark.anyio
async def test_failed_cycle_is_sanitized_and_api_continues(caplog):
    stop = asyncio.Event()
    def failure(*, limit):
        raise RuntimeError("private-key recipient data")
    # Stop after the failed cycle, without waiting for a production interval.
    task = asyncio.create_task(lifecycle.run_delivery(SimpleNamespace(dispatch_batch=failure), stop, 30))
    for _ in range(100):
        if caplog.records:
            break
        await asyncio.sleep(0.01)
    stop.set()
    await asyncio.wait_for(task, 3)
    assert "Falha no processamento" in caplog.text
    assert "private-key" not in caplog.text and "recipient data" not in caplog.text
