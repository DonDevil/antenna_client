"""Unit tests for lightweight client-side chat routing rules."""

from utils.chat_message_handler import ChatMessageHandler


def test_classify_design_request_by_frequency_tokens() -> None:
    msg = "Create a 4.0 GHz microstrip patch antenna with 300 MHz bandwidth"
    assert ChatMessageHandler.classify_user_message(msg) == "design_request"


def test_classify_design_request_by_keywords_only() -> None:
    msg = "please optimize this antenna design"
    assert ChatMessageHandler.classify_user_message(msg) == "design_request"


def test_classify_capability_question() -> None:
    msg = "what substrate materials and families are supported"
    assert ChatMessageHandler.classify_user_message(msg) == "capability_question"


def test_classify_vague_input() -> None:
    msg = "help me"
    assert ChatMessageHandler.classify_user_message(msg) == "vague_input"


def test_classify_general_chat() -> None:
    msg = "hello there can you explain your workflow"
    assert ChatMessageHandler.classify_user_message(msg) == "general_chat"
