#!/usr/bin/env python
"""
Management script for the backend application.
"""
import argparse
import asyncio
import importlib
import os
import sys
from typing import List

# Ensure commands are imported
from commands import get_command, get_available_commands

def import_commands():
    """Import all command modules to register them"""
    commands_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands")
    for filename in os.listdir(commands_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module = filename[:-3]  # Remove .py extension
            importlib.import_module(f"commands.{module}")

async def execute_command(name: str, args: List[str]):
    """Execute a command by name with given arguments"""
    try:
        command_class = get_command(name)
        command = command_class()
        parser = command.create_parser("manage.py", name)
        
        # Parse arguments
        options = parser.parse_args(args)
        
        # Execute the command
        result = await command.handle(**vars(options))
        if result:
            print(result)
            
    except Exception as e:
        print(f"Error executing command {name}: {e}", file=sys.stderr)
        sys.exit(1)

def print_help():
    """Print help message with available commands"""
    print("Usage: python manage.py <command> [options]")
    print()
    print("Available commands:")
    
    commands = get_available_commands()
    for name, command_class in sorted(commands.items()):
        command = command_class()
        print(f"  {name:<20} {command.help}")

def main():
    """Main entry point"""
    # Import command modules
    import_commands()
    
    # Parse the first argument (command name)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?")
    
    # Parse only the command name
    args, remaining_args = parser.parse_known_args()
    
    if not args.command or args.command == "help":
        print_help()
        return
    
    # Execute the command
    try:
        asyncio.run(execute_command(args.command, remaining_args))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
