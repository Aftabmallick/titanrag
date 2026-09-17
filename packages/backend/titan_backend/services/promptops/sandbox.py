import re
from typing import Any

from jinja2 import StrictUndefined, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

# Disallowed built-in function and attribute names in AST
DISALLOWED_NAMES = {
    "__import__",
    "open",
    "eval",
    "exec",
    "compile",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
    "os",
    "sys",
    "subprocess",
}

DISALLOWED_ATTR_PREFIXES = ("_",)


class SecurityViolation(ValueError):
    pass


class SandboxedPromptEngine:
    def __init__(self) -> None:
        self.env = SandboxedEnvironment(
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def validate_template_syntax(self, template_str: str) -> None:
        """Ensures template parses as valid Jinja2 and contains no prohibited constructs."""
        try:
            self.env.parse(template_str)
        except TemplateSyntaxError as e:
            raise ValueError(f"Jinja2 template syntax error at line {e.lineno}: {e.message}") from e

        # Scan template for suspicious identifiers
        for match in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", template_str):
            identifier = match.group(1)
            if identifier in DISALLOWED_NAMES:
                raise SecurityViolation(f"Use of restricted keyword or function '{identifier}' is strictly forbidden.")

    def render_prompt(self, template_str: str, context: dict[str, Any]) -> str:
        """Renders prompt inside secure sandbox with context."""
        self.validate_template_syntax(template_str)
        template = self.env.from_string(template_str)
        return template.render(**context)


sandbox = SandboxedPromptEngine()
