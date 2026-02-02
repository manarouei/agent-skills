"""
Command registry system for management commands.
"""
from typing import Dict, Type
from .base import BaseCommand

# Registry to store all available commands
_commands: Dict[str, Type[BaseCommand]] = {}

def register_command(name: str, command_class: Type[BaseCommand]) -> None:
    """Register a command with the management system"""
    _commands[name] = command_class

def get_command(name: str) -> Type[BaseCommand]:
    """Get a command by name"""
    if name not in _commands:
        raise ValueError(f"Command '{name}' not found. Available commands: {list(_commands.keys())}")
    return _commands[name]

def get_available_commands() -> Dict[str, Type[BaseCommand]]:
    """Get all registered commands"""
    return _commands
