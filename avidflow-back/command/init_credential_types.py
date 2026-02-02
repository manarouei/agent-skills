#!/usr/bin/env python
"""
Initialization script to populate credential types table with default values.
Run this after migrations but before starting the application.
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import CredentialType

# Import the credentials package to get all credential definitions
from credentials import get_all_credentials

async def init_credential_types(session: AsyncSession):
    """Initialize credential types in the database - Delete all and recreate"""
    try:
        # Delete all existing credential types
        delete_query = delete(CredentialType)
        result = await session.execute(delete_query)
        deleted_count = result.rowcount
        print(f"Deleted {deleted_count} existing credential types")
        
        # Get credential type definitions from the credentials package
        credential_types = get_all_credentials()
        
        # Add all credential types fresh
        for cred_type in credential_types:
            # Create new credential type
            new_type = CredentialType(
                id=str(uuid.uuid4()),
                name=cred_type["name"],
                display_name=cred_type["display_name"],
                properties=cred_type["properties"],
                is_oauth2=cred_type.get("is_oauth2", False),
                is_active=True
            )
            session.add(new_type)
            print(f"Added credential type: {cred_type['name']}")
        
        # Commit all changes
        await session.commit()
        print(f"Successfully recreated {len(credential_types)} credential types")
        return True, "Credential types initialization completed."
        
    except Exception as e:
        await session.rollback()
        return False, f"Error initializing credential types: {str(e)}"