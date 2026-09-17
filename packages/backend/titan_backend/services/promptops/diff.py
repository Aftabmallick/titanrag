import difflib
from typing import Any

import tiktoken

_tokenizer = None


def get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        try:
            _tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _tokenizer = None
    return _tokenizer


def count_tokens(text: str) -> int:
    enc = get_tokenizer()
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # Approximate fallback: 4 chars per token
    return max(1, len(text) // 4)


def compute_prompt_diff(old_content: str, new_content: str) -> dict[str, Any]:
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="version_a",
            tofile="version_b",
            lineterm="",
        )
    )

    old_tokens = count_tokens(old_content)
    new_tokens = count_tokens(new_content)

    return {
        "diff_unified": "\n".join(diff),
        "old_token_count": old_tokens,
        "new_token_count": new_tokens,
        "token_delta": new_tokens - old_tokens,
        "percent_change": round(((new_tokens - old_tokens) / old_tokens * 100) if old_tokens > 0 else 0.0, 2),
    }
