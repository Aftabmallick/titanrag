from typing import Annotated

import typer

from titan_mcp.server import create_mcp_server

cli = typer.Typer(
    name="titan-mcp",
    help="TitanRAG Model Context Protocol (MCP) Server for Cursor and Claude Desktop",
    no_args_is_help=False,
)


@cli.command()
def main(
    transport: Annotated[str, typer.Option("--transport", "-t", help="MCP transport: 'stdio' or 'sse'")] = "stdio",
    port: Annotated[int, typer.Option("--port", "-p", help="Port for SSE transport")] = 8080,
    host: Annotated[str, typer.Option("--host", "-h", help="Host address for SSE transport")] = "0.0.0.0",
) -> None:
    """Launch the TitanRAG MCP server."""
    server = create_mcp_server()

    if transport.lower() == "stdio":
        server.run(transport="stdio")
    elif transport.lower() == "sse":
        server.settings.port = port
        server.settings.host = host
        server.run(transport="sse")
    else:
        typer.echo(f"Unsupported transport: {transport}. Choose 'stdio' or 'sse'.", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    main()
