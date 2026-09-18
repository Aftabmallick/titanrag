from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from titanrag.cli.config import get_active_client, load_config, save_config
from titanrag.exceptions import TitanRAGError

console = Console()
auth_app = typer.Typer(help="Authentication and profile commands")


@auth_app.command("login")
def login(
    api_key: Annotated[str | None, typer.Option("--api-key", "-k", help="TitanRAG API Key (tr_...)")] = None,
    base_url: Annotated[str | None, typer.Option("--base-url", "-u", help="TitanRAG Server URL")] = None,
) -> None:
    """Authenticate with TitanRAG platform and store credentials in ~/.titan/config.json."""
    cfg = load_config()
    target_url = base_url or cfg.get("base_url") or "http://localhost:8000"

    key = api_key
    if not key:
        key = typer.prompt("Enter your TitanRAG API Key", hide_input=True)

    console.print(f"[dim]Verifying credentials against {target_url}...[/dim]")
    client = get_active_client(override_base_url=target_url, override_api_key=key)

    try:
        # Check workspaces endpoint to verify credentials
        workspaces = client.workspaces.list()
        cfg["base_url"] = target_url
        cfg["api_key"] = key
        if workspaces and not cfg.get("active_workspace_id"):
            cfg["active_workspace_id"] = str(workspaces[0].id)
        save_config(cfg)

        console.print(Panel(
            f"[bold green]Authentication Successful![/bold green]\n"
            f"Server: [cyan]{target_url}[/cyan]\n"
            f"Accessible Workspaces: [yellow]{len(workspaces)}[/yellow]\n"
            f"Default Workspace: [white]{cfg.get('active_workspace_id', 'None')}[/white]",
            title="TitanRAG Login",
        ))
    except TitanRAGError as e:
        console.print(f"[bold red]Login Failed:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@auth_app.command("whoami")
def whoami() -> None:
    """Display active authentication configuration and selected workspace."""
    cfg = load_config()
    if not cfg.get("api_key") and not cfg.get("token"):
        console.print("[yellow]Not logged in. Run 'titan login' first.[/yellow]")
        raise typer.Exit(code=1)

    key_masked = cfg["api_key"][:6] + "..." + cfg["api_key"][-4:] if cfg.get("api_key") else "None"

    console.print(Panel(
        f"Server: [cyan]{cfg.get('base_url', 'http://localhost:8000')}[/cyan]\n"
        f"API Key: [white]{key_masked}[/white]\n"
        f"Active Workspace: [yellow]{cfg.get('active_workspace_id', 'None selected')}[/yellow]",
        title="Active Profile",
    ))


@auth_app.command("logout")
def logout() -> None:
    """Clear local credentials from ~/.titan/config.json."""
    save_config({})
    console.print("[green]Successfully logged out and cleared config.[/green]")
