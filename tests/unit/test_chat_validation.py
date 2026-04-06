#!/usr/bin/env python3
"""Test chat message validation"""

from utils.chat_message_handler import ChatMessageHandler
from ui.chat_widget import ChatWidget

# Create a mock chat widget
chat = ChatWidget()

# Create handler
handler = ChatMessageHandler(chat)

print("Testing message validation:\n")

# Test 1: Too short
print("Test 1: Message too short (5 chars)")
handler.handle_user_message("hello")
print(f"Chat messages: {len(chat.messages)}")
if chat.messages:
    print(f"Last message: {chat.messages[-1]['text'][:50]}...")
print()

# Test 2: Valid message
print("Test 2: Valid message (> 10 chars)")
handler.handle_user_message("I need a 2.4 GHz antenna")
print(f"Chat messages: {len(chat.messages)}")
if chat.messages:
    print(f"Last message: {chat.messages[-1]['text'][:50]}...")
print()

# Test 3: Another short message
print("Test 3: Another short message (7 chars)")
handler.handle_user_message("antenna")
print(f"Chat messages: {len(chat.messages)}")
if chat.messages:
    print(f"Last message: {chat.messages[-1]['text'][:50]}...")
print()

print("✅ Validation tests complete")
