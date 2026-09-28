import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.src.database import get_db
from api.src.models.db_models import UserPreference
from api.src.models.schemas import (
    UserPreferenceCreate,
    UserPreferenceUpdate,
    UserPreferenceResponse,
)
from api.src.services.cache_service import cache_service

logger = logging.getLogger("api.preferences")
router = APIRouter(prefix="/api/preferences", tags=["User Preferences"])


@router.get("/{email}", response_model=UserPreferenceResponse, summary="Get User Preferences")
async def get_preferences(email: str, db: AsyncSession = Depends(get_db)):
    clean_email = email.lower().strip()

    # Try Cache First
    cached = await cache_service.get_user_preferences(clean_email)
    if cached:
        return UserPreferenceResponse(**cached)

    # Database Fallback
    result = await db.execute(
        select(UserPreference).where(UserPreference.email == clean_email)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User preferences for '{clean_email}' not found.",
        )

    # Warm Cache
    await cache_service.set_user_preferences(clean_email, prefs.to_dict())
    return prefs


@router.post("", response_model=UserPreferenceResponse, status_code=status.HTTP_201_CREATED, summary="Create User Preferences")
async def create_preferences(payload: UserPreferenceCreate, db: AsyncSession = Depends(get_db)):
    clean_email = payload.email.lower().strip()

    result = await db.execute(
        select(UserPreference).where(UserPreference.email == clean_email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Preferences for email '{clean_email}' already exist.",
        )

    new_prefs = UserPreference(
        user_id=payload.user_id,
        email=clean_email,
        email_opt_out=payload.email_opt_out,
        preferred_language=payload.preferred_language,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(new_prefs)
    await db.commit()
    await db.refresh(new_prefs)

    # Cache
    await cache_service.set_user_preferences(clean_email, new_prefs.to_dict())
    return new_prefs


@router.put("/{email}", response_model=UserPreferenceResponse, summary="Update User Preferences")
async def update_preferences(
    email: str,
    payload: UserPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    clean_email = email.lower().strip()

    result = await db.execute(
        select(UserPreference).where(UserPreference.email == clean_email)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create on the fly if does not exist
        prefs = UserPreference(
            user_id=f"usr-{uuid.uuid4().hex[:8]}",
            email=clean_email,
            email_opt_out=payload.email_opt_out if payload.email_opt_out is not None else False,
            preferred_language=payload.preferred_language if payload.preferred_language is not None else "en",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(prefs)
    else:
        if payload.email_opt_out is not None:
            prefs.email_opt_out = payload.email_opt_out
        if payload.preferred_language is not None:
            prefs.preferred_language = payload.preferred_language
        prefs.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(prefs)

    # Warm / update cache
    await cache_service.set_user_preferences(clean_email, prefs.to_dict())
    return prefs
