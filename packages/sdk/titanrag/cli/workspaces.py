import json
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from titanrag.cli.config import get_active_client, get_active_workspace_id, load_config, save_config
from titanrag.exceptions import TitanRAGError

console = Console()
workspace_app = typer.Typer(help="Manage TitanRAG workspaces")


@workspace_app.command("list")
def list_workspaces(
    as_json: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
) -> None:
    """List all accessible workspaces in the current tenant."""
    client = get_active_client()
    try:
        workspaces = client.workspaces.list()
        active_id = get_active_workspace_id()

        if as_json:
            typer.echo(json.dumps([w.model_dump(mode="json") for w in workspaces], indent=2))
            return

        table = Table(title="TitanRAG Workspaces", show_lines=True)
        table.add_column("Status", justify="center", style="bold")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold white")
        table.add_column("Slug", style="green")
        table.add_column("Description", style="dim")

        for w in workspaces:
            is_active = str(w.id) == str(active_id)
            status_symbol = "[bold green]★ ACTIVE[/bold green]" if is_active else "[dim]—[/dim]"
            table.add_row(status_symbol, str(w.id), w.name, w.slug, w.description or "—")

        console.print(table)
    except TitanRAGError as e:
        console.print(f"[bold red]Error listing workspaces:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@workspace_app.command("create")
def create_workspace(
    name: Annotated[str, typer.Argument(help="Workspace name")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Description")] = None,
    switch: Annotated[bool, typer.Option("--switch", "-s", help="Immediately switch to the new workspace")] = True,
) -> None:
    """Create a new workspace."""
    client = get_active_client()
    try:
        w = client.workspaces.create(name=name, description=description)
        console.print(f"[bold green]Workspace created:[/bold green] {w.name} ([cyan]{w.id}[/cyan])")

        if switch:
            cfg = load_config()
            cfg["active_workspace_id"] = str(w.id)
            save_config(cfg)
            console.print(f"[green]Switched active workspace to:[/green] {w.name}")
    except TitanRAGError as e:
        console.print(f"[bold red]Error creating workspace:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@workspace_app.command("switch")
def switch_workspace(
    workspace_id: Annotated[str, typer.Argument(help="Workspace ID or Slug to set as default")],
) -> None:
    """Set the active workspace ID for subsequent CLI commands."""
    client = get_active_client()
    try:
        workspaces = client.workspaces.list()
        match = None
        for w in workspaces:
            if str(w.id) == workspace_id or w.slug == workspace_id:
                match = w
                break

        if not match:
            console.print(f"[bold red]Workspace '{workspace_id}' not found among accessible workspaces.[/bold red]")
            raise typer.Exit(code=1)

        cfg = load_config()
        cfg["active_workspace_id"] = str(match.id)
        save_config(cfg)
        console.print(f"[bold green]Switched active workspace to:[/bold green] {match.name} ([cyan]{match.id}[/cyan])")
    except TitanRAGError as e:
        console.print(f"[bold red]Error switching workspace:[/bold red] {e}")
        raise typer.Exit(code=1) from None
