import json
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from titanrag.cli.config import get_active_client, get_active_workspace_id
from titanrag.exceptions import TitanRAGError

console = Console()
settings_app = typer.Typer(help="Manage workspace RAG settings")


def _resolve_workspace_id(override_id: str | None) -> str:
    wid = get_active_workspace_id(override_id)
    if not wid:
        console.print(
            "[bold red]No active workspace selected. Use 'titan workspace switch <id>' or pass '--workspace-id'.[/bold red]"
        )
        raise typer.Exit(code=1)
    return wid


@settings_app.command("get")
def get_settings(
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
) -> None:
    """Display active RAG settings for the workspace."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    try:
        s = client.settings.get(wid)
        if as_json:
            typer.echo(json.dumps(s.model_dump(mode="json"), indent=2))
            return

        table = Table(title=f"RAG Settings: Workspace {wid[:8]}...", show_lines=True)
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="bold white")

        table.add_row("Retrieval Mode", s.retrieval_mode)
        table.add_row("Dense Weight (Semantic)", str(s.dense_weight))
        table.add_row("Sparse Weight (BM25)", str(s.sparse_weight))
        table.add_row("Top-K Retrieved", str(s.top_k))
        table.add_row("Top-N Reranked", str(s.rerank_top_k))
        table.add_row("Confidence Threshold", str(s.score_threshold))
        table.add_row("HyDE Generation", "Enabled" if s.hyde_enabled else "Disabled")
        table.add_row("Semantic Cache", "Enabled" if s.semantic_cache_enabled else "Disabled")

        console.print(table)
    except TitanRAGError as e:
        console.print(f"[bold red]Error fetching settings:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@settings_app.command("set")
def update_settings(
    pairs: Annotated[list[str], typer.Argument(help="Key=Value configuration pairs (e.g. dense_weight=0.8 top_k=30)")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
) -> None:
    """Update RAG parameters for the workspace."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    updates: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            console.print(f"[bold red]Invalid format '{pair}'. Expected key=value.[/bold red]")
            raise typer.Exit(code=1)
        k, v = pair.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Parse numbers / booleans
        if v.lower() == "true":
            parsed_v: Any = True
        elif v.lower() == "false":
            parsed_v = False
        else:
            try:
                parsed_v = int(v)
            except ValueError:
                try:
                    parsed_v = float(v)
                except ValueError:
                    parsed_v = v
        updates[k] = parsed_v

    try:
        client.settings.update(wid, **updates)
        console.print(
            Panel(
                f"[bold green]Updated {len(updates)} setting(s) successfully![/bold green]\n"
                + "\n".join(f"• [cyan]{k}[/cyan] = [bold white]{v}[/bold white]" for k, v in updates.items()),
                title="Settings Saved",
            )
        )
    except TitanRAGError as e:
        console.print(f"[bold red]Error updating settings:[/bold red] {e}")
        raise typer.Exit(code=1) from None
