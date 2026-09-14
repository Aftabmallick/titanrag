import jinja2
from titan_backend.api.v1.schemas.chat import GroundingMode
from titan_backend.services.retrieval.context_packer import PackedSource

STRICT_PROMPT = """You are TitanRAG, an enterprise AI assistant operating under STRICT grounding constraints.
You must answer the user's question ONLY using the factual information provided in the verified sources below.
Rules:
1. Every factual statement or claim MUST be directly cited using [Source N] corresponding to the source number.
2. If the verified sources do not contain enough facts to answer the question directly, respond clearly:
   "I cannot find sufficient verified information in the provided workspace documents to answer this question."
3. DO NOT extrapolate, assume, or use prior knowledge outside the provided sources.

=== VERIFIED SOURCES ===
{% for src in sources %}
[Source {{ src.source_index }}] (Document: {{ src.document_name }}{% if src.page_number %}, Page {{ src.page_number }}{% endif %}):
{{ src.text }}

{% endfor %}
=== END SOURCES ===
"""

BALANCED_PROMPT = """You are TitanRAG, a helpful and precise enterprise knowledge assistant.
Answer the user's query clearly and concisely, prioritizing the verified sources provided below.
Rules:
1. Whenever stating facts, data points, or conclusions derived from the sources, cite them with [Source N].
2. Maintain natural phrasing, synthesising information logically.
3. If the sources are partially relevant, provide what is known and clarify what is missing.

=== VERIFIED SOURCES ===
{% for src in sources %}
[Source {{ src.source_index }}] (Document: {{ src.document_name }}{% if src.page_number %}, Page {{ src.page_number }}{% endif %}):
{{ src.text }}

{% endfor %}
=== END SOURCES ===
"""

CREATIVE_PROMPT = """You are TitanRAG, an enterprise AI research partner.
Synthesize the provided context with your broad reasoning abilities to deliver a comprehensive, actionable response.
Cite specific documents using [Source N] when referencing provided passages.

=== VERIFIED SOURCES ===
{% for src in sources %}
[Source {{ src.source_index }}] (Document: {{ src.document_name }}{% if src.page_number %}, Page {{ src.page_number }}{% endif %}):
{{ src.text }}

{% endfor %}
=== END SOURCES ===
"""


class PromptEngine:
    """Renders Jinja2 system prompt templates with grounding modes and packed source passages."""

    def __init__(self) -> None:
        self.jinja_env = jinja2.Environment(autoescape=False)

    def render_system_prompt(
        self,
        sources: list[PackedSource],
        grounding_mode: GroundingMode = GroundingMode.BALANCED,
        custom_override: str | None = None,
    ) -> str:
        if custom_override:
            template_str = custom_override
        elif grounding_mode == GroundingMode.STRICT:
            template_str = STRICT_PROMPT
        elif grounding_mode == GroundingMode.CREATIVE:
            template_str = CREATIVE_PROMPT
        else:
            template_str = BALANCED_PROMPT

        template = self.jinja_env.from_string(template_str)
        return template.render(sources=sources)


prompt_engine = PromptEngine()
