import tiktoken
from titan_backend.core.logging import logger


class TokenBudgetManager:
    """Manages token budgets across system prompt, retrieved sources, and chat history using tiktoken."""

    def __init__(self, default_encoding: str = "cl100k_base"):
        try:
            self.encoder = tiktoken.get_encoding(default_encoding)
        except Exception:
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def truncate_chat_history(
        self,
        chat_history: list[dict[str, str]],
        max_history_tokens: int = 1500,
    ) -> list[dict[str, str]]:
        """Keeps newest conversation messages that fit within max_history_tokens."""
        if not chat_history:
            return []

        kept: list[dict[str, str]] = []
        total_tokens = 0

        # Traverse backwards from newest to oldest
        for msg in reversed(chat_history):
            content = msg.get("content", "")
            tokens = self.count_tokens(content) + 4  # Overhead per message
            if total_tokens + tokens > max_history_tokens:
                logger.debug("chat_history_truncated", kept=len(kept), dropped_tokens=tokens)
                break
            total_tokens += tokens
            kept.append(msg)

        # Restore original chronological order
        kept.reverse()
        return kept


token_budget_manager = TokenBudgetManager()
