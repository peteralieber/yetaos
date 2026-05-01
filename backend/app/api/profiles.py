from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_registry
from app.profiles.registry import ProfileRegistry
from app.profiles.resolver import ProfileResolver
from app.schemas import ResolveProfilesResponse

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("")
async def list_profiles(
    registry: ProfileRegistry = Depends(get_registry),
    category: str | None = Query(default=None),
) -> list[dict[str, object]]:
    profiles = registry.load_all()
    if category:
        return [p.model_dump() for p in profiles.values() if p.category == category]
    return [p.model_dump() for p in profiles.values()]


@router.get("/resolve", response_model=ResolveProfilesResponse)
async def resolve(
    profile_string: str,
    registry: ProfileRegistry = Depends(get_registry),
) -> ResolveProfilesResponse:
    resolver = ProfileResolver(registry.load_all())
    try:
        resolved = resolver.resolve_from_string(profile_string)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ResolveProfilesResponse(requested=profile_string, resolved_profiles=resolved)
