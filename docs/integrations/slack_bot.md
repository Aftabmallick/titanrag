# Slack Bot Integration: TitanRAG

Build an enterprise knowledge assistant for Slack using [Slack Bolt for Python](https://slack.dev/bolt-python/) and `titanrag.SyncTitanClient`.

---

## 1. Prerequisites & Installation

```bash
pip install titanrag slack-bolt
```

Create a Slack App at [api.slack.com/apps](https://api.slack.com/apps) with:
- **Bot Token Scopes**: `app_mentions:read`, `chat:write`
- **Socket Mode**: Enabled (generates `SLACK_APP_TOKEN`)

---

## 2. Implementation (`slack_bot.py`)

```python
import os
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from titanrag import SyncTitanClient
from titanrag.exceptions import TitanRAGError

# Initialize Slack App
app = App(token=os.environ["SLACK_BOT_TOKEN"])

# Initialize TitanRAG SDK
titan = SyncTitanClient(
    api_key=os.environ["TITANRAG_API_KEY"],
    base_url=os.environ.get("TITANRAG_API_URL", "http://localhost:8000"),
)

WORKSPACE_ID = os.environ["TITANRAG_WORKSPACE_ID"]


@app.event("app_mention")
def handle_app_mention(event, say, client):
    """Handle @TitanRAG bot mentions in public or private channels."""
    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])
    raw_text = event["text"]

    # Strip bot user mention e.g. <@U12345678>
    clean_query = re.sub(r"<@[A-Z0-9]+>", "", raw_text).strip()

    if not clean_query:
        say(text="Hi! Ask me anything about our enterprise documentation.", thread_ts=thread_ts)
        return

    # Post initial placeholder
    placeholder = say(
        text="🔍 *Searching enterprise knowledge base and synthesizing answer...*",
        thread_ts=thread_ts,
    )

    try:
        # Query TitanRAG
        response = titan.chat.create(
            workspace_id=WORKSPACE_ID,
            message=clean_query,
        )

        answer_text = response.get("answer", "No answer could be generated.")
        citations = response.get("citations", [])

        # Build Slack Block Kit UI
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": answer_text,
                },
            },
        ]

        if citations:
            source_lines = []
            for c in citations[:5]:
                title = c.get("title") or c.get("filename") or "Document"
                score = round(float(c.get("score", 0)) * 100)
                source_lines.append(f"• *{title}* (Relevance: {score}%)")

            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "📚 *Sources:*\n" + "\n".join(source_lines),
                    }
                ],
            })

        # Update message in place
        client.chat_update(
            channel=channel,
            ts=placeholder["ts"],
            text=answer_text,
            blocks=blocks,
        )

    except TitanRAGError as err:
        client.chat_update(
            channel=channel,
            ts=placeholder["ts"],
            text=f"❌ *TitanRAG Error:* {str(err)}",
        )


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡️ TitanRAG Slack Bot is running in Socket Mode!")
    handler.start()
```

---

## 3. Running with Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY slack_bot.py .
CMD ["python", "slack_bot.py"]
```
