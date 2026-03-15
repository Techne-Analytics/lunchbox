from fastapi import APIRouter

from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(prefix="/api/schools", tags=["schools"])


@router.get("")
def search_schools(q: str) -> list[dict]:
    with SchoolCafeClient() as client:
        schools = client.search_schools(q)
    return [{"school_id": s.school_id, "school_name": s.school_name} for s in schools]
