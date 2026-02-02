"""
Command to create a superuser for the admin interface.
"""
import argparse
import getpass
import bcrypt
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from commands.base import BaseCommand
from database.models import AdminUser
from . import register_command

class CreateSuperUserCommand(BaseCommand):
    """Command to create a superuser"""
    
    name = "createsuperuser"
    help = "Create a superuser for the admin interface"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add command-specific arguments"""
        parser.add_argument("--username", "-u", help="Specify the username")
        parser.add_argument("--password", "-p", help="Specify the password (not recommended, use interactive mode)")
        parser.add_argument("--non-interactive", "-n", action="store_true", help="Run in non-interactive mode")
    
    async def validate_username(self, session: AsyncSession, username: str) -> tuple[bool, str]:
        """Check if the username already exists"""
        query = select(AdminUser).where(AdminUser.username == username)
        result = await session.execute(query)
        user = result.scalars().first()
        if user:
            return False, f"Username '{username}' is already taken."
        return True, ""
    
    async def handle(self, *args: Any, **options: Any) -> Optional[str]:
        """Execute the command"""
        from database.config import get_async_session
        
        interactive = not options.get("non_interactive", False)
        username = options.get("username")
        password = options.get("password")
        
        if not interactive and (not username or not password):
            return "In non-interactive mode, both username and password must be provided."

        async for session in get_async_session():
            # In interactive mode, prompt for credentials
            if interactive:
                while not username:
                    username = input("Username: ")
                    is_valid, message = await self.validate_username(session, username)
                    if not is_valid:
                        print(message)
                        username = None
                
                while not password:
                    password = getpass.getpass("Password: ")
                    password_confirm = getpass.getpass("Password (confirm): ")
                    
                    if password != password_confirm:
                        print("Passwords don't match. Please try again.")
                        password = None
                    elif len(password) < 8:
                        print("Password must be at least 8 characters long.")
                        password = None
            else:
                # Non-interactive mode - validate the provided credentials
                is_valid, message = await self.validate_username(session, username)
                if not is_valid:
                    return message
                
                if not password or len(password) < 8:
                    return "Password must be at least 8 characters long."
            
            # Hash the password
            hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            
            # Create the superuser
            admin_user = AdminUser(
                username=username,
                hashed_password=hashed_password,
                is_superuser=True,
                is_active=True
            )
            
            try:
                session.add(admin_user)
                await session.commit()
                return f"Superuser '{username}' created successfully."
            except Exception as e:
                await session.rollback()
                return f"Error creating superuser: {str(e)}"

# Register the command
register_command(CreateSuperUserCommand.name, CreateSuperUserCommand)
