"""Chat API endpoint for the FinAlly AI assistant."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import add_chat_message, get_chat_history
from app.llm import process_chat_message

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.get("/chat/history")
def get_chat_history_endpoint():
    """Return the chat message history for the default user.

    Returns a list of messages with id, role, content, actions, and created_at.
    """
    return get_chat_history("default", limit=50)


@router.post("/chat")
def chat(request: ChatRequest):
    """Send a message to the AI assistant and receive a structured response.

    Saves the user message to chat history, calls the LLM service, saves the
    assistant response with executed actions, and returns the result to the client.

    Returns:
        {
            "message": str,
            "trades_executed": [{ticker, side, quantity, price, success, error}],
            "watchlist_changes_made": [{ticker, action, success}],
            "errors": [str]
        }
    """
    # Save user message to history
    add_chat_message("default", "user", request.message)

    # Process with LLM (and auto-execute any trades/watchlist changes)
    result = process_chat_message(request.message)

    # Save assistant response with executed actions (use same keys as response)
    actions = {
        "trades": result["trades"],
        "watchlist_changes": result["watchlist_changes"],
    }
    add_chat_message("default", "assistant", result["message"], actions)

    return result
