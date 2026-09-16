import { test, describe } from "node:test";
import assert from "node:assert/strict";

describe("Phased SSE Stream State Machine & Parser", () => {
  // Test parsing SSE chunk blocks
  function parseSseBlock(raw: string): { event: string; data: any }[] {
    const events: { event: string; data: any }[] = [];
    const blocks = raw.split("\n\n");

    for (const block of blocks) {
      if (!block.trim()) continue;
      let eventType = "message";
      let dataStr = "";

      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) {
          eventType = line.substring(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.substring(6).trim();
        }
      }

      if (dataStr) {
        try {
          events.push({ event: eventType, data: JSON.parse(dataStr) });
        } catch {
          // invalid json ignored
        }
      }
    }
    return events;
  }

  test("correctly parses retrieval_status event", () => {
    const raw = `event: retrieval_status\ndata: {"message": "Searching Qdrant dense vector store..."}\n\n`;
    const parsed = parseSseBlock(raw);
    assert.equal(parsed.length, 1);
    assert.equal(parsed[0].event, "retrieval_status");
    assert.equal(parsed[0].data.message, "Searching Qdrant dense vector store...");
  });

  test("correctly accumulates streaming tokens sequentially", () => {
    const raw = `event: token\ndata: {"token": "Section "}\n\nevent: token\ndata: {"token": "12.4 states "}\n\nevent: token\ndata: {"token": "liability is capped."}\n\n`;
    const parsed = parseSseBlock(raw);
    assert.equal(parsed.length, 3);
    const fullText = parsed.map((p) => p.data.token).join("");
    assert.equal(fullText, "Section 12.4 states liability is capped.");
  });

  test("processes citation and citation_verified events with NLI entailment scores", () => {
    const raw = [
      `event: citation`,
      `data: {"citations": [{"source_index": 1, "document_name": "Agreement.pdf", "page_number": 4, "snippet": "Liability shall not exceed $1M."}]}`,
      ``,
      `event: citation_verified`,
      `data: {"average_entailment": 0.94, "verified_citations": [1]}`,
      ``,
      `event: done`,
      `data: {"total_tokens": 142, "latency_ms": 1180}`,
      ``,
    ].join("\n");

    const parsed = parseSseBlock(raw);
    assert.equal(parsed.length, 3);

    // Citation payload
    assert.equal(parsed[0].event, "citation");
    assert.equal(parsed[0].data.citations[0].source_index, 1);
    assert.equal(parsed[0].data.citations[0].document_name, "Agreement.pdf");

    // Verification payload
    assert.equal(parsed[1].event, "citation_verified");
    assert.equal(parsed[1].data.average_entailment, 0.94);
    assert.deepEqual(parsed[1].data.verified_citations, [1]);

    // Done payload
    assert.equal(parsed[2].event, "done");
    assert.equal(parsed[2].data.total_tokens, 142);
    assert.equal(parsed[2].data.latency_ms, 1180);
  });

  test("parses inline citation references in markdown", () => {
    const text = "The agreement states that liability is capped at $1M [^1], subject to exceptions in clause 4 [Source 2].";
    const regex = /\[(?:\^|Source\s+)(\d+)\]/g;
    const matches: number[] = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      matches.push(parseInt(match[1], 10));
    }

    assert.deepEqual(matches, [1, 2]);
  });
});
