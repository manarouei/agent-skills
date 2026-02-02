"""
Base command class for all management commands.
"""
import argparse
from abc import ABC, abstractmethod
from typing import Any, Optional, Sequence

class BaseCommand(ABC):
    """Base class for management commands"""
    
    # Command name (used in help text)
    name: str = ""
    
    # Command help text
    help: str = ""
    
    def __init__(self):
        self.parser = None
    
    def create_parser(self, prog_name: str, command_name: str) -> argparse.ArgumentParser:
        """Create the command parser"""
        parser = argparse.ArgumentParser(
            prog=f"{prog_name} {command_name}",
            description=self.help or None,
        )
        self.add_arguments(parser)
        return parser
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Add custom arguments to the parser.
        Override this method to add arguments to the command.
        """
        pass
    
    @abstractmethod
    async def handle(self, *args: Any, **options: Any) -> Optional[str]:
        """
        Execute the command.
        This method must be implemented by all command classes.
        
        Returns:
            Optional message to display after command execution.
        """
        pass
