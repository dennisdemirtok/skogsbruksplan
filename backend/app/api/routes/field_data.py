import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.field_data import FieldData, SoilMoisture
from app.models.property import Property
from app.models.stand import Stand
from app.models.user import User

router = APIRouter(prefix="/fielddata", tags=["fielddata"])

UPLOAD_DIR = Path("/app/data/uploads")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SampleTree(BaseModel):
    species: str
    dbh_cm: float
    height_m: float


class NatureValues(BaseModel):
    dead_wood: Optional[bool] = None
    red_listed_species: Optional[list[str]] = None
    key_biotope: Optional[bool] = None


class FieldDataCreateRequest(BaseModel):
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    relascope_value: Optional[float] = Field(
        None, description="Relaskoptal m2/ha"
    )
    sample_trees: Optional[list[SampleTree]] = None
    soil_moisture: Optional[SoilMoisture] = None
    nature_values: Optional[NatureValues] = None
    photos: Optional[list[str]] = None
    notes: Optional[str] = None
    recorded_at: Optional[datetime] = None


class FieldDataUpdateRequest(BaseModel):
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    relascope_value: Optional[float] = None
    sample_trees: Optional[list[SampleTree]] = None
    soil_moisture: Optional[SoilMoisture] = None
    nature_values: Optional[NatureValues] = None
    photos: Optional[list[str]] = None
    notes: Optional[str] = None


class FieldDataResponse(BaseModel):
    id: uuid.UUID
    stand_id: uuid.UUID
    recorded_by: uuid.UUID
    recorded_at: datetime
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    relascope_value: Optional[float] = None
    sample_trees: Optional[list[dict[str, Any]]] = None
    soil_moisture: Optional[SoilMoisture] = None
    nature_values: Optional[dict[str, Any]] = None
    photos: Optional[list[str]] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class PhotoUploadResponse(BaseModel):
    filename: str
    url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_stand_access(
    stand_id: uuid.UUID, user: User, db: AsyncSession
) -> Stand:
    """Verify that the stand exists and the user has access to its property."""
    result = await db.execute(select(Stand).where(Stand.id == stand_id))
    stand = result.scalar_one_or_none()
    if not stand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avdelningen hittades inte",
        )

    result = await db.execute(
        select(Property).where(Property.id == stand.property_id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fastigheten hittades inte",
        )
    if prop.owner_id != user.id and prop.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Åtkomst nekad",
        )
    return stand


def _field_data_to_response(fd: FieldData) -> FieldDataResponse:
    return FieldDataResponse(
        id=fd.id,
        stand_id=fd.stand_id,
        recorded_by=fd.recorded_by,
        recorded_at=fd.recorded_at,
        gps_lat=fd.gps_lat,
        gps_lon=fd.gps_lon,
        relascope_value=fd.relascope_value,
        sample_trees=fd.sample_trees,
        soil_moisture=fd.soil_moisture,
        nature_values=fd.nature_values,
        photos=fd.photos,
        notes=fd.notes,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/stand/{stand_id}",
    response_model=list[FieldDataResponse],
    summary="List field data for a stand",
)
async def list_field_data_for_stand(
    stand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all field data entries for the given stand, ordered by
    recording date descending (newest first)."""
    await _verify_stand_access(stand_id, current_user, db)

    result = await db.execute(
        select(FieldData)
        .where(FieldData.stand_id == stand_id)
        .order_by(FieldData.recorded_at.desc())
    )
    entries = result.scalars().all()
    return [_field_data_to_response(fd) for fd in entries]


@router.post(
    "/stand/{stand_id}",
    response_model=FieldDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create field data entry for a stand",
)
async def create_field_data(
    stand_id: uuid.UUID,
    request: FieldDataCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a new field observation for the specified stand."""
    await _verify_stand_access(stand_id, current_user, db)

    recorded_at = request.recorded_at or datetime.now(timezone.utc)

    field_data = FieldData(
        id=uuid.uuid4(),
        stand_id=stand_id,
        recorded_by=current_user.id,
        recorded_at=recorded_at,
        gps_lat=request.gps_lat,
        gps_lon=request.gps_lon,
        relascope_value=request.relascope_value,
        sample_trees=(
            [t.model_dump() for t in request.sample_trees]
            if request.sample_trees
            else None
        ),
        soil_moisture=request.soil_moisture,
        nature_values=(
            request.nature_values.model_dump(exclude_none=True)
            if request.nature_values
            else None
        ),
        photos=request.photos,
        notes=request.notes,
    )

    db.add(field_data)
    await db.flush()
    await db.refresh(field_data)

    return _field_data_to_response(field_data)


@router.get(
    "/{field_data_id}",
    response_model=FieldDataResponse,
    summary="Get a single field data entry",
)
async def get_field_data(
    field_data_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single field data entry by its ID."""
    result = await db.execute(
        select(FieldData).where(FieldData.id == field_data_id)
    )
    fd = result.scalar_one_or_none()
    if not fd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fältdata hittades inte",
        )
    await _verify_stand_access(fd.stand_id, current_user, db)
    return _field_data_to_response(fd)


@router.put(
    "/{field_data_id}",
    response_model=FieldDataResponse,
    summary="Update a field data entry",
)
async def update_field_data(
    field_data_id: uuid.UUID,
    request: FieldDataUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing field data entry.  Only fields that are
    explicitly provided will be modified."""
    result = await db.execute(
        select(FieldData).where(FieldData.id == field_data_id)
    )
    fd = result.scalar_one_or_none()
    if not fd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fältdata hittades inte",
        )
    await _verify_stand_access(fd.stand_id, current_user, db)

    update_data = request.model_dump(exclude_unset=True)

    # Convert nested Pydantic models to dicts for JSON columns
    if "sample_trees" in update_data and update_data["sample_trees"] is not None:
        update_data["sample_trees"] = [
            t.model_dump() if isinstance(t, SampleTree) else t
            for t in update_data["sample_trees"]
        ]
    if "nature_values" in update_data and update_data["nature_values"] is not None:
        nv = update_data["nature_values"]
        update_data["nature_values"] = (
            nv.model_dump(exclude_none=True)
            if isinstance(nv, NatureValues)
            else nv
        )

    for field, value in update_data.items():
        setattr(fd, field, value)

    await db.flush()
    await db.refresh(fd)

    return _field_data_to_response(fd)


@router.delete(
    "/{field_data_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a field data entry",
)
async def delete_field_data(
    field_data_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a field data entry by its ID."""
    result = await db.execute(
        select(FieldData).where(FieldData.id == field_data_id)
    )
    fd = result.scalar_one_or_none()
    if not fd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fältdata hittades inte",
        )
    await _verify_stand_access(fd.stand_id, current_user, db)
    await db.delete(fd)
    await db.flush()


@router.post(
    "/photo",
    response_model=PhotoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a field photo",
)
async def upload_photo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
):
    """Upload a photo and save it to /app/data/uploads/ with a UUID-based
    filename.  Returns the URL path that can be stored in a field data
    entry's ``photos`` list."""
    if file.content_type not in (
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Otillåten filtyp. Tillåtna: JPEG, PNG, WebP, HEIC",
        )

    # Derive a safe extension from the content type
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }
    extension = ext_map.get(file.content_type, ".jpg")
    file_id = uuid.uuid4()
    filename = f"{file_id}{extension}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / filename

    async with aiofiles.open(file_path, "wb") as out:
        while chunk := await file.read(1024 * 64):  # 64 KB chunks
            await out.write(chunk)

    url = f"/uploads/{filename}"

    return PhotoUploadResponse(filename=filename, url=url)
