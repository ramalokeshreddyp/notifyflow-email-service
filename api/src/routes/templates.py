import logging
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.src.database import get_db
from api.src.models.db_models import NotificationTemplate
from api.src.models.schemas import TemplateCreate, TemplateUpdate, TemplateResponse
from api.src.services.cache_service import cache_service

logger = logging.getLogger("api.templates")
router = APIRouter(prefix="/api/templates", tags=["Templates"])


@router.get("", response_model=List[TemplateResponse], summary="List All Templates")
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationTemplate))
    templates = result.scalars().all()
    return templates


@router.get("/{template_id}", response_model=TemplateResponse, summary="Get Template by ID")
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    # Try Cache First
    cached = await cache_service.get_template(template_id)
    if cached:
        return TemplateResponse(**cached)

    # Database Fallback
    result = await db.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found.",
        )

    # Warm Cache
    await cache_service.set_template(template_id, template.to_dict())
    return template


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED, summary="Create Template")
async def create_template(payload: TemplateCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == payload.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with ID '{payload.id}' already exists.",
        )

    new_template = NotificationTemplate(
        id=payload.id,
        name=payload.name,
        subject_template=payload.subject_template,
        body_template=payload.body_template,
        language=payload.language,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)

    # Cache the newly created template
    await cache_service.set_template(payload.id, new_template.to_dict())
    return new_template


@router.put("/{template_id}", response_model=TemplateResponse, summary="Update Template")
async def update_template(
    template_id: str,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found.",
        )

    if payload.name is not None:
        template.name = payload.name
    if payload.subject_template is not None:
        template.subject_template = payload.subject_template
    if payload.body_template is not None:
        template.body_template = payload.body_template
    if payload.language is not None:
        template.language = payload.language
    template.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(template)

    # Invalidate and update cache
    await cache_service.set_template(template_id, template.to_dict())
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Template")
async def delete_template(template_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found.",
        )

    await db.delete(template)
    await db.commit()

    # Invalidate Cache
    await cache_service.delete_template(template_id)
    return None
