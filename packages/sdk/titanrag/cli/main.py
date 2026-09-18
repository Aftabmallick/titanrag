import typer
from rich.console import Console

from titanrag.cli.auth import auth_app, login, logout, whoami
from titanrag.cli.chat import chat_app, interactive_chat, query
from titanrag.cli.documents import doc_app, upload_documents
from titanrag.cli.plugins import plugin_app
from titanrag.cli.settings import settings_app
from titanrag.cli.workspaces import workspace_app

console = Console()

app = typer.Typer(
    name="titan",
    help="TitanRAG Developer CLI — Stream, Ingest, and Automate RAG Workflows",
    no_args_is_help=True,
)

# Sub-command groups
app.add_typer(auth_app, name="auth", help="Manage authentication and profiles")
app.add_typer(workspace_app, name="workspace", help="Manage workspaces")
app.add_typer(doc_app, name="documents", help="Manage documents and ingestion")
app.add_typer(chat_app, name="chat", help="Chat and query operations")
app.add_typer(settings_app, name="settings", help="Manage RAG configuration")
app.add_typer(plugin_app, name="plugins", help="Manage webhook micro-hook plugins")

# Top-level direct shortcut commands for high-frequency workflows
app.command("login", help="Authenticate with TitanRAG platform")(login)
app.command("whoami", help="Display active profile and workspace")(whoami)
app.command("logout", help="Clear local credentials")(logout)
app.command("upload", help="Upload documents to active workspace")(upload_documents)
app.command("query", help="Query knowledge base with streaming terminal markdown")(query)
app.command("repl", help="Start interactive terminal chat session")(interactive_chat)


@app.command("version")
def version() -> None:
    """Print TitanRAG CLI and SDK version."""
    from titanrag import __version__

    console.print(f"[bold cyan]TitanRAG CLI[/bold cyan] version [bold white]{__version__}[/bold white]")


if __name__ == "__main__":
    app()
