"""Chat API endpoint for the FinAlly AI assistant."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import add_chat_message
from app.llm import process_chat_message

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str


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

    # Save assistant response with executed actions
    actions = {
        "trades_executed": result["trades_executed"],
        "watchlist_changes_made": result["watchlist_changes_made"],
    }
    add_chat_message("default", "assistant", result["message"], actions)

    return result
