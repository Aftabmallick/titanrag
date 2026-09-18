import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger("titanrag.integrations.agent_actions")


@dataclass
class ActionToolDefinition:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    requires_confirmation: bool = False


ACTION_TOOLS: dict[str, ActionToolDefinition] = {
    "create_jira_issue": ActionToolDefinition(
        name="create_jira_issue",
        description="Creates a Jira issue or bug ticket with summary, description, and project key.",
        parameters_schema={
            "type": "object",
            "properties": {
                "project_key": {"type": "string", "description": "Jira Project Key e.g. PROJ"},
                "summary": {"type": "string", "description": "Issue title summary"},
                "description": {"type": "string", "description": "Detailed description"},
                "issue_type": {"type": "string", "default": "Task"},
            },
            "required": ["project_key", "summary", "description"],
        },
        requires_confirmation=True,
    ),
    "send_slack_notification": ActionToolDefinition(
        name="send_slack_notification",
        description="Sends a formatted notification message to a designated Slack channel.",
        parameters_schema={
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Target Slack channel name or ID"},
                "message": {"type": "string", "description": "Notification message text"},
                "urgency": {"type": "string", "enum": ["low", "normal", "high"], "default": "normal"},
            },
            "required": ["channel", "message"],
        },
        requires_confirmation=False,
    ),
    "export_google_sheet": ActionToolDefinition(
        name="export_google_sheet",
        description="Exports tabular RAG data rows directly to a Google Sheets document.",
        parameters_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Spreadsheet document title"},
                "headers": {"type": "array", "items": {"type": "string"}},
                "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            },
            "required": ["title", "headers", "rows"],
        },
        requires_confirmation=True,
    ),
}


class AgentActionManager:
    """
    Manages LLM agent action tools execution with Human-in-the-loop (HITL) confirmation.
    """

    # In-memory pending confirmations storage (persisted across sessions via token)
    _pending_confirmations: dict[str, dict[str, Any]] = {}

    @classmethod
    def list_available_tools(cls) -> list[dict[str, Any]]:
        """Return tools in OpenAI function calling / tool specification format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
                "requires_confirmation": tool.requires_confirmation,
            }
            for tool in ACTION_TOOLS.values()
        ]

    @classmethod
    async def execute_action(
        cls,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: str,
        workspace_id: str,
        bypass_confirmation: bool = False,
    ) -> dict[str, Any]:
        tool = ACTION_TOOLS.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown action tool: '{tool_name}'")

        if tool.requires_confirmation and not bypass_confirmation:
            confirm_id = f"act_{uuid.uuid4().hex[:12]}"
            cls._pending_confirmations[confirm_id] = {
                "tool_name": tool_name,
                "arguments": arguments,
                "user_id": user_id,
                "workspace_id": workspace_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
            return {
                "status": "requires_confirmation",
                "confirmation_id": confirm_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "message": f"Action '{tool_name}' requires explicit user confirmation before executing.",
            }

        # Simulated real execution of the action
        logger.info("executing_agent_action", tool=tool_name, user_id=user_id, arguments=arguments)
        return {
            "status": "executed",
            "tool_name": tool_name,
            "executed_at": datetime.now(UTC).isoformat(),
            "result": {
                "message": f"Successfully executed action {tool_name}",
                "output_id": f"res_{uuid.uuid4().hex[:8]}",
            },
        }

    @classmethod
    async def confirm_action(cls, confirmation_id: str, approved: bool) -> dict[str, Any]:
        pending = cls._pending_confirmations.pop(confirmation_id, None)
        if not pending:
            raise ValueError("Confirmation request not found or expired")

        if not approved:
            return {
                "status": "rejected",
                "confirmation_id": confirmation_id,
                "message": "Action was cancelled by user.",
            }

        return await cls.execute_action(
            tool_name=pending["tool_name"],
            arguments=pending["arguments"],
            user_id=pending["user_id"],
            workspace_id=pending["workspace_id"],
            bypass_confirmation=True,
        )
