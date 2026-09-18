import json
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from titanrag.cli.config import get_active_client, get_active_workspace_id
from titanrag.exceptions import TitanRAGError
from titanrag.models import Citation, CitationEvent, DoneEvent, ErrorEvent, StatusEvent, TokenEvent

console = Console()
chat_app = typer.Typer(help="Chat and query commands")


def _resolve_workspace_id(override_id: str | None) -> str:
    wid = get_active_workspace_id(override_id)
    if not wid:
        console.print(
            "[bold red]No active workspace selected. Use 'titan workspace switch <id>' or pass '--workspace-id'.[/bold red]"
        )
        raise typer.Exit(code=1)
    return wid


def _render_citations(citations: list[Citation]) -> None:
    if not citations:
        return
    table = Table(title="Retrieved Citations & Sources", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Document", style="bold white")
    table.add_column("Page", justify="center", width=6)
    table.add_column("Snippet Preview", style="dim")

    for idx, c in enumerate(citations, 1):
        snippet = (c.snippet[:120] + "...") if len(c.snippet) > 120 else c.snippet
        table.add_row(
            f"[{idx}]",
            c.filename or str(c.document_id)[:8],
            str(c.page or 1),
            snippet.replace("\n", " "),
        )
    console.print(table)


@chat_app.command("query")
def query(
    prompt: Annotated[str, typer.Argument(help="Question or prompt to submit to RAG pipeline")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    grounding_mode: Annotated[
        str, typer.Option("--mode", "-m", help="Grounding mode: Strict, Balanced, Creative")
    ] = "Balanced",
    no_stream: Annotated[bool, typer.Option("--no-stream", help="Wait for full response instead of streaming")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output raw JSON response")] = False,
    session_id: Annotated[str | None, typer.Option("--session-id", "-s", help="Existing chat session ID")] = None,
) -> None:
    """Submit a query to the TitanRAG knowledge engine with streaming terminal output."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    if no_stream or as_json:
        try:
            resp = client.query(
                query=prompt,
                workspace_id=wid,
                session_id=session_id,
                grounding_mode=grounding_mode,
            )
            if as_json:
                typer.echo(json.dumps(resp.model_dump(mode="json"), indent=2))
            else:
                console.print(Markdown(resp.answer))
                _render_citations(resp.citations)
        except TitanRAGError as e:
            console.print(f"[bold red]Query failed:[/bold red] {e}")
            raise typer.Exit(code=1) from None
        return

    # Streaming mode
    try:
        accumulated_text = ""
        citations: list[Citation] = []
        follow_ups: list[str] = []

        console.print(f"[dim]Connecting to workspace {wid[:8]}...[/dim]")

        for event in client.chat_stream(
            query=prompt,
            workspace_id=wid,
            session_id=session_id,
            grounding_mode=grounding_mode,
        ):
            if isinstance(event, StatusEvent):
                console.print(f"[dim italic]{event.message}...[/dim italic]")
            elif isinstance(event, TokenEvent):
                sys.stdout.write(event.token)
                sys.stdout.flush()
                accumulated_text += event.token
            elif isinstance(event, CitationEvent):
                citations.append(event.citation)
            elif isinstance(event, DoneEvent):
                follow_ups = event.follow_up_questions
            elif isinstance(event, ErrorEvent):
                console.print(f"\n[bold red]Stream error:[/bold red] {event.error}")

        sys.stdout.write("\n\n")
        sys.stdout.flush()

        if citations:
            _render_citations(citations)

        if follow_ups:
            console.print("[bold cyan]Suggested follow-ups:[/bold cyan]")
            for f in follow_ups:
                console.print(f" • [dim]{f}[/dim]")

    except TitanRAGError as e:
        console.print(f"[bold red]Streaming query failed:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@chat_app.command("chat")
def interactive_chat(
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    grounding_mode: Annotated[
        str, typer.Option("--mode", "-m", help="Grounding mode: Strict, Balanced, Creative")
    ] = "Balanced",
) -> None:
    """Launch an interactive multi-turn terminal chat session with TitanRAG."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    console.print(
        Panel(
            f"[bold]TitanRAG Interactive REPL[/bold]\n"
            f"Workspace: [cyan]{wid}[/cyan] | Mode: [yellow]{grounding_mode}[/yellow]\n"
            f"Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to end session.",
            title="Interactive Session",
        )
    )

    session_id: str | None = None

    while True:
        try:
            user_input = typer.prompt("\n[titanrag]> ")
            if user_input.strip().lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            if not user_input.strip():
                continue

            # Stream response
            citations: list[Citation] = []
            for event in client.chat_stream(
                query=user_input,
                workspace_id=wid,
                session_id=session_id,
                grounding_mode=grounding_mode,
            ):
                if isinstance(event, TokenEvent):
                    sys.stdout.write(event.token)
                    sys.stdout.flush()
                elif isinstance(event, CitationEvent):
                    citations.append(event.citation)
                elif isinstance(event, DoneEvent):
                    if event.session_id:
                        session_id = event.session_id

            sys.stdout.write("\n")
            sys.stdout.flush()
            if citations:
                _render_citations(citations)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session terminated.[/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
