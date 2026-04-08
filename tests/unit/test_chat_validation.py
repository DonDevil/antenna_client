"""Unit tests for chat message handling behavior."""

from __future__ import annotations

from typing import Any, Callable

import utils.chat_message_handler as handler_module
from utils.chat_message_handler import ChatMessageHandler


class _SignalStub:
    def __init__(self) -> None:
        self._callbacks: list[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        self._callbacks.append(callback)


class _ChatWidgetStub:
    def __init__(self) -> None:
        self.message_submitted = _SignalStub()
        self.messages: list[dict[str, str]] = []

    def add_message(self, text: str, sender: str) -> None:
        self.messages.append({"text": text, "sender": sender})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self.messages)


class _DesignPanelStub:
    def __init__(self) -> None:
        self.start_pipeline_requested = _SignalStub()
        self.reset_requested = _SignalStub()
        self.export_requested = _SignalStub()
        self.feedback_requested = _SignalStub()

    def set_spec_values(self, frequency_ghz=None, bandwidth_mhz=None, antenna_family=None) -> None:
        return None

    def get_specs(self) -> dict[str, Any]:
        return {
            "frequency_ghz": 2.4,
            "bandwidth_mhz": 100.0,
            "antenna_family": "microstrip_patch",
        }


class _StatusBarStub:
    def __init__(self) -> None:
        self.messages: list[tuple[str, int]] = []

    def show_message(self, message: str, timeout_ms: int = 5000) -> None:
        self.messages.append((message, timeout_ms))


class _FakeWorker:
    last_instance: "_FakeWorker | None" = None

    def __init__(self, user_message: str, requirements: dict[str, Any], chat_mode: str = "speed"):
        self.user_message = user_message
        self.requirements = requirements
        self.chat_mode = chat_mode
        self.response_ready = _SignalStub()
        self.error_occurred = _SignalStub()
        self.started = False
        _FakeWorker.last_instance = self

    def start(self) -> None:
        self.started = True


def _make_handler() -> tuple[ChatMessageHandler, _StatusBarStub]:
    chat = _ChatWidgetStub()
    panel = _DesignPanelStub()
    status = _StatusBarStub()
    return ChatMessageHandler(chat, panel, status), status


def test_short_message_is_sent_to_chat_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(handler_module, "ChatRequestWorker", _FakeWorker)
    _FakeWorker.last_instance = None
    handler, status = _make_handler()

    handler.handle_user_message("hello")

    assert _FakeWorker.last_instance is not None
    assert _FakeWorker.last_instance.user_message == "hello"
    assert _FakeWorker.last_instance.chat_mode == "quality"
    assert _FakeWorker.last_instance.started is True
    assert status.messages[-1][0] == "Sending message to assistant..."


def test_blank_message_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr(handler_module, "ChatRequestWorker", _FakeWorker)
    _FakeWorker.last_instance = None
    handler, status = _make_handler()

    handler.handle_user_message("   ")

    assert _FakeWorker.last_instance is None
    assert status.messages == []
