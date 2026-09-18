/**
 * Lightweight, secure markdown renderer for the TitanRAG chat widget.
 * Sanitizes input and compiles markdown to HTML without external dependencies.
 */

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}

export function renderMarkdown(markdown: string): string {
  if (!markdown) return "";

  // 1. Separate code blocks first to protect formatting
  const codeBlocks: string[] = [];
  let processed = markdown.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    const escaped = escapeHtml(code.trim());
    codeBlocks.push(
      `<pre class="code-block"><div class="code-header"><span>${escapeHtml(lang || "text")}</span><button class="copy-btn" data-code="${escapeHtml(code.trim())}">Copy</button></div><code>${escaped}</code></pre>`
    );
    return `__CODE_BLOCK_${idx}__`;
  });

  // 2. Escape HTML
  processed = escapeHtml(processed);

  // 3. Inline formatting
  // Inline code
  processed = processed.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
  // Bold
  processed = processed.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // Italics
  processed = processed.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  // Citation pills: [^N] or [Source N]
  processed = processed.replace(/\[\^(\d+)\]/g, '<button class="cite-pill" data-cite-idx="$1">[$1]</button>');
  processed = processed.replace(/\[Source\s+(\d+)\]/gi, '<button class="cite-pill" data-cite-idx="$1">[Source $1]</button>');

  // Links
  processed = processed.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

  // Bullet lists
  processed = processed.replace(/^\s*[-*]\s+(.*)$/gm, "<li>$1</li>");
  processed = processed.replace(/(<li>.*<\/li>(\n|$))+/g, '<ul class="chat-list">$&</ul>');

  // Paragraphs & Linebreaks
  const paragraphs = processed.split(/\n\n+/);
  processed = paragraphs
    .map((p) => {
      const trimmed = p.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("<pre") || trimmed.startsWith("<ul")) return trimmed;
      return `<p>${trimmed.replace(/\n/g, "<br/>")}</p>`;
    })
    .join("");

  // Re-inject code blocks
  processed = processed.replace(/__CODE_BLOCK_(\d+)__/g, (_, idx) => codeBlocks[Number(idx)] || "");

  return processed;
}
