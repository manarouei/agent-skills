"""
Command to initialize credential types in the database.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Optional
from commands.base import BaseCommand
from database.config import get_async_session
from command.init_credential_types import init_credential_types
from . import register_command

class InitCredentialTypesCommand(BaseCommand):
    """Command to initialize credential types"""
    
    name = "init_credential_types"
    help = "Initialize credential types in the database"
    
    async def handle(self, *args: Any, **options: Any) -> Optional[str]:
        """Execute the command"""
        async for session in get_async_session():
            try:
                async with session:
                    success, message = await init_credential_types(session)
                    if not success:
                        return f"Error: {message}"
                    return message
            except Exception as e:
                return f"An error occurred: {str(e)}"

# Register the command
register_command(InitCredentialTypesCommand.name, InitCredentialTypesCommand)
