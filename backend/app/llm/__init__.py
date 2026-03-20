"""LLM subsystem for FinAlly AI chat assistant.

Public API::

    process_chat_message - Process a user message and return structured response
                           with any auto-executed trades and watchlist changes.
"""

from .service import process_chat_message

__all__ = ["process_chat_message"]
