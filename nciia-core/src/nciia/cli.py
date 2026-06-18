"""
N-CIIA Command Line Interface
"""

import argparse
import asyncio
import sys


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="nciia",
        description="N-CIIA - National Cyber Investigation & Intelligence Assistant",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Start API server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host address")
    server_parser.add_argument("--port", type=int, default=8000, help="Port number")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    
    # Version command
    version_parser = subparsers.add_parser("version", help="Show version")
    
    args = parser.parse_args()
    
    if args.command == "server":
        from nciia.api.server import run
        run()
    elif args.command == "init":
        asyncio.run(init_database())
    elif args.command == "version":
        from nciia import __version__
        print(f"N-CIIA version {__version__}")
    else:
        parser.print_help()


async def init_database():
    """Initialize the database."""
    from nciia.db import get_database, close_database
    from nciia.utils import get_settings
    
    settings = get_settings()
    print(f"Initializing database at: {settings.database.path}")
    
    db = await get_database(settings.database.path)
    print("Database initialized successfully!")
    
    await close_database()


if __name__ == "__main__":
    main()
