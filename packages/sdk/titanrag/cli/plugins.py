import json
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from titanrag.cli.config import get_active_client, get_active_workspace_id
from titanrag.exceptions import TitanRAGError

console = Console()
plugin_app = typer.Typer(help="Manage webhook micro-hook plugins")


def _resolve_workspace_id(override_id: str | None) -> str:
    wid = get_active_workspace_id(override_id)
    if not wid:
        console.print("[bold red]No active workspace selected. Use 'titan workspace switch <id>' or pass '--workspace-id'.[/bold red]")
        raise typer.Exit(code=1)
    return wid


@plugin_app.command("list")
def list_plugins(
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
) -> None:
    """List registered webhook plugins."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    try:
        plugins = client.plugins.list(wid)
        if as_json:
            typer.echo(json.dumps([p.model_dump(mode="json") for p in plugins], indent=2))
            return

        table = Table(title=f"Plugins in Workspace {wid[:8]}...", show_lines=True)
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold white")
        table.add_column("Hooks", style="yellow")
        table.add_column("Health", style="green")
        table.add_column("Endpoint URL", style="dim")

        for p in plugins:
            health_color = "green" if p.health_status == "HEALTHY" else "red"
            hooks_str = ", ".join(p.hooks) if p.hooks else "none"
            table.add_row(
                str(p.id)[:8] + "...",
                p.name,
                hooks_str,
                f"[{health_color}]{p.health_status}[/{health_color}]",
                p.endpoint_url,
            )

        console.print(table)
    except TitanRAGError as e:
        console.print(f"[bold red]Error listing plugins:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@plugin_app.command("ping")
def ping_plugin(
    plugin_id: Annotated[str, typer.Argument(help="Plugin UUID")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
) -> None:
    """Send an immediate test probe to verify plugin connectivity and HMAC signature."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    console.print(f"[dim]Pinging plugin {plugin_id[:8]}...[/dim]")
    try:
        res = client.plugins.ping(workspace_id=wid, plugin_id=plugin_id)
        if res.get("success"):
            console.print(f"[bold green]✓ Ping Successful![/bold green] Status: {res.get('status_code')} | Latency: [cyan]{res.get('latency_ms')} ms[/cyan]")
        else:
            console.print(f"[bold red]✗ Ping Failed:[/bold red] {res.get('error')} (Status: {res.get('status_code')})")
    except TitanRAGError as e:
        console.print(f"[bold red]Error pinging plugin:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@plugin_app.command("register")
def register_plugin(
    name: Annotated[str, typer.Argument(help="Plugin name")],
    endpoint_url: Annotated[str, typer.Argument(help="Remote HTTPS webhook URL")],
    hooks: Annotated[str, typer.Argument(help="Comma-separated hooks, e.g. ON_PARSE,ON_POST_GENERATE")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    timeout_ms: Annotated[int, typer.Option("--timeout", "-t", help="Timeout in ms")] = 2000,
) -> None:
    """Register a new webhook micro-hook plugin."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    hook_list = [h.strip() for h in hooks.split(",")]

    try:
        res = client.plugins.register(
            workspace_id=wid,
            name=name,
            endpoint_url=endpoint_url,
            hooks=hook_list,
            timeout_ms=timeout_ms,
        )
        console.print("[bold green]Plugin Registered Successfully![/bold green]")
        console.print(f"ID: [cyan]{res.get('id')}[/cyan]")
        console.print(f"Webhook Secret: [bold red]{res.get('webhook_secret')}[/bold red] (Copy now! This will not be shown again)")
    except TitanRAGError as e:
        console.print(f"[bold red]Error registering plugin:[/bold red] {e}")
        raise typer.Exit(code=1) from None
