from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from database import crud, models
from models.credential import (
    CredentialCreate,
    CredentialUpdate,
    CredentialResponse,
    CredentialType,
    CredentialTest,
)
from database.models import User
from auth.dependencies import get_current_user
from utils.encryption import encrypt_credential_data, decrypt_credential_data
from .workflow import get_db_from_app
from credentials import CREDENTIAL_TYPES
import uuid
from fastapi_pagination import Page, Params

router = APIRouter()


# Get all credential types
@router.get("/types", response_model=List[CredentialType])
async def get_credential_types(
    db: AsyncSession = Depends(get_db_from_app),
    active_only: bool = Query(True, description="Only return active credential types"),
):
    """Get all available credential types from database"""
    credential_types = await crud.CredentialTypeCRUD.get_all_credential_types(
        db, active_only=active_only
    )

    # Convert from DB model to response model
    result = []
    for ctype in credential_types:
        result.append(
            {
                "name": ctype.name,
                "displayName": ctype.display_name,
                "properties": ctype.properties,
                "is_oauth2": ctype.is_oauth2,
            }
        )

    # Return empty list if no types found
    if not result:
        # Log warning - this shouldn't happen in production
        print("Warning: No credential types found in database!")

    return result


@router.get("/types/{type_name}", response_model=CredentialType)
async def get_credential_type(
    type_name: str,
    db: AsyncSession = Depends(get_db_from_app),
):
    """Get a specific credential type by name"""
    credential_type = await crud.CredentialTypeCRUD.get_credential_type_by_name(
        db, type_name
    )
    if not credential_type:
        raise HTTPException(status_code=404, detail="اطلاعات اعتبارنامه یافت نشد.")
    return credential_type


# Get all credentials for the current user
@router.get("/", response_model=Page[CredentialResponse])
async def get_credentials(
    params: Params = Depends(),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get all credentials for the current user with pagination"""
    credentials = await crud.CredentialCRUD.get_all_credentials(
        db, current_user.id, params
    )

    return credentials


# Get a specific credential
@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get a specific credential by ID"""
    credential = await crud.CredentialCRUD.get_credential(db, credential_id)

    if not credential or credential.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="اعتبارنامه یافت نشد")

    # Decrypt data
    decrypted_data = decrypt_credential_data(credential.data)

    return CredentialResponse(
        id=credential.id,
        name=credential.name,
        type=credential.type,
        data=decrypted_data,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


# Create a new credential
@router.post(
    "/", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED
)
async def create_credential(
    credential_data: CredentialCreate,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Create a new credential"""
    # Encrypt sensitive data
    encrypted_data = encrypt_credential_data(credential_data.data)

    # Create credential in database
    credential_id = str(uuid.uuid4())

    new_credential = models.Credential(
        id=credential_id,
        name=credential_data.name,
        type=credential_data.type,
        data=encrypted_data,
        user_id=current_user.id,
    )

    db.add(new_credential)
    await db.commit()
    await db.refresh(new_credential)

    # Return credential with decrypted data for immediate use
    return CredentialResponse(
        id=new_credential.id,
        name=new_credential.name,
        type=new_credential.type,
        data=credential_data.data,  # Return original unencrypted data
        created_at=new_credential.created_at,
        updated_at=new_credential.updated_at,
        ownedBy={
            "id": current_user.id,
            "firstName": current_user.first_name,
            "lastName": current_user.last_name,
            "email": current_user.email,
        },
    )


# Update a credential
@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: str,
    credential_update: CredentialUpdate,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Update an existing credential"""
    # Check if credential exists and belongs to user
    credential = await crud.CredentialCRUD.get_credential(db, credential_id)

    if not credential or credential.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="اعتبارنامه یافت نشد")

    # Update fields
    if credential_update.name is not None:
        credential.name = credential_update.name

    if credential_update.data is not None:
        credential.data = encrypt_credential_data(credential_update.data)

    await db.commit()
    await db.refresh(credential)

    # Return updated credential
    return CredentialResponse(
        id=credential.id,
        name=credential.name,
        type=credential.type,
        data=decrypt_credential_data(credential.data),
        created_at=credential.created_at,
        updated_at=credential.updated_at,
        ownedBy={
            "id": current_user.id,
            "firstName": current_user.first_name,
            "lastName": current_user.last_name,
            "email": current_user.email,
        },
    )


# Delete a credential
@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Delete a credential"""
    # Check if credential exists and belongs to user
    credential = await crud.CredentialCRUD.get_credential(db, credential_id)

    if not credential or credential.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="اعتبارنامه یافت نشد")

    # Delete credential
    await db.delete(credential)
    await db.commit()

    return None


# Test a credential
@router.post("/test", status_code=status.HTTP_200_OK)
async def test_credential(
    credential_test: CredentialTest,
    current_user: User = Depends(get_current_user),
):
    """Test if a credential is valid"""
    credential_class = CREDENTIAL_TYPES.get(credential_test.type)
    if not credential_class:
        raise HTTPException(status_code=400, detail="نوع اعتبارنامه نامعتبر است")
    result = await credential_class(data=credential_test.data).test()
    return result


# Get credentials by type for the current user
@router.get("/by-type/{credential_type}", response_model=List[CredentialResponse])
async def get_credentials_by_type(
    credential_type: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get all credentials of a specific type for the current user"""
    credentials = await crud.CredentialCRUD.get_credentials_by_type(
        db, current_user.id, credential_type
    )

    # Decrypt data before returning
    result = []
    for cred in credentials:
        result.append(
            CredentialResponse(
                id=cred.id,
                name=cred.name,
                type=cred.type,
                created_at=cred.created_at,
                updated_at=cred.updated_at,
            )
        )

    return result
