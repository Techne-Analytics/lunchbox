import logging

from fastapi import APIRouter

from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(prefix="/api/schools", tags=["schools"])

logger = logging.getLogger(__name__)


@router.get("")
def search_schools(q: str) -> list[dict]:
    try:
        with SchoolCafeClient() as client:
            schools = client.search_schools(q)
    except Exception:
        logger.exception("School search failed for query: %s", q)
        return []
    return [{"school_id": s.school_id, "school_name": s.school_name} for s in schools]
