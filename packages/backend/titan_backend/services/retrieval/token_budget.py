from dataclasses import dataclass

import tiktoken
from titan_backend.core.logging import logger
from titan_backend.services.retrieval.context_packer import PackedSource

# Standard model context window caps
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-haiku-20240307": 200_000,
    "deepseek-ai/deepseek-v4-flash-0731": 64_000,
    "deepseek-chat": 64_000,
    "meta-llama/llama-3.1-70b-instruct": 128_000,
    "meta-llama/llama-3.1-8b-instruct": 128_000,
}
DEFAULT_CONTEXT_WINDOW = 8_192


@dataclass
class BudgetAllocation:
    total_window: int
    system_prompt_budget: int
    completion_reserve: int
    context_sources_budget: int
    chat_history_budget: int


class TokenBudgetManager:
    """Enterprise token budget manager enforcing strict context limits across

    system prompt, retrieved sources, chat history, and completion reserve.
    """

    def __init__(self, default_encoding: str = "cl100k_base"):
        try:
            self.encoder = tiktoken.get_encoding(default_encoding)
        except Exception:
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            return len(self.encoder.encode(text))
        except Exception:
            # Fallback heuristic: 1 token ~ 4 chars
            return max(1, len(text) // 4)

    def get_context_window(self, model: str | None) -> int:
        if not model:
            return DEFAULT_CONTEXT_WINDOW
        model_clean = model.lower().strip()
        for k, v in MODEL_CONTEXT_LIMITS.items():
            if k in model_clean:
                return v
        return DEFAULT_CONTEXT_WINDOW

    def calculate_budget_allocation(
        self,
        model: str | None = None,
        system_prompt: str = "",
        max_output_tokens: int = 2000,
        history_ratio: float = 0.25,
    ) -> BudgetAllocation:
        """Dynamically computes budget limits based on model context window."""
        total_window = self.get_context_window(model)

        # Cap total operational window to prevent extreme memory/cost explosions
        # (e.g. clamp 200k down to 32k or 64k operational window for standard RAG)
        operational_window = min(total_window, 32_768)

        sys_tokens = self.count_tokens(system_prompt) + 10  # Overhead
        completion_reserve = max_output_tokens

        remaining_for_content = max(500, operational_window - sys_tokens - completion_reserve)

        # Split remaining between context sources (75%) and chat history (25%)
        history_budget = int(remaining_for_content * history_ratio)
        context_budget = remaining_for_content - history_budget

        return BudgetAllocation(
            total_window=operational_window,
            system_prompt_budget=sys_tokens,
            completion_reserve=completion_reserve,
            context_sources_budget=context_budget,
            chat_history_budget=history_budget,
        )

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

        kept.reverse()
        return kept

    def fit_sources_to_budget(
        self,
        sources: list[PackedSource],
        max_context_tokens: int,
    ) -> list[PackedSource]:
        """Filters and truncates sources to fit within max_context_tokens while

        retaining top-ranked items in priority order.
        """
        fitted: list[PackedSource] = []
        accumulated_tokens = 0

        for s in sources:
            s_tokens = self.count_tokens(s.text) + 20  # Overhead for source citation header
            if accumulated_tokens + s_tokens <= max_context_tokens:
                fitted.append(s)
                accumulated_tokens += s_tokens
            else:
                # If we have space for a partial source (> 100 tokens), truncate it
                remaining = max_context_tokens - accumulated_tokens
                if remaining > 100 and not fitted:
                    truncated_text = s.text[: remaining * 4]
                    fitted.append(
                        PackedSource(
                            source_index=s.source_index,
                            chunk_id=s.chunk_id,
                            document_id=s.document_id,
                            document_name=s.document_name,
                            page_number=s.page_number,
                            bbox=s.bbox,
                            text=truncated_text + "... [truncated to fit token budget]",
                            relevance_score=s.relevance_score,
                        )
                    )
                break

        return fitted


token_budget_manager = TokenBudgetManager()
