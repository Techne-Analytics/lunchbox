import logging
import uuid
from pathlib import Path

from markupsafe import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from fastapi import HTTPException

from lunchbox.auth.dependencies import get_current_user
from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import MenuItem, Subscription, User
from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(tags=["web"])
logger = logging.getLogger(__name__)
_here = Path(__file__).parent
templates = Jinja2Templates(directory=str(_here / "templates"))


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(request, "landing.html", {"user": None})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscriptions = db.query(Subscription).filter(Subscription.user_id == user.id).all()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "subscriptions": subscriptions,
            "base_url": settings.base_url,
        },
    )


@router.get("/subscriptions/new", response_class=HTMLResponse)
def new_subscription(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "subscription_new.html", {"user": user})


@router.post("/subscriptions/create")
async def create_subscription_web(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Guardrail: subscription caps (same checks as API endpoint)
    user_count = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.is_active.is_(True))
        .count()
    )
    if user_count >= settings.max_subscriptions_per_user:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_subscriptions_per_user} active subscriptions per user",
        )
    global_count = (
        db.query(Subscription).filter(Subscription.is_active.is_(True)).count()
    )
    if global_count >= settings.max_subscriptions_global:
        raise HTTPException(
            status_code=400, detail="Maximum active subscriptions reached"
        )

    form = await request.form()
    school_id = form.get("school_id", "")
    school_name = form.get("school_name") or school_id

    meals = form.getlist("meals")
    meal_configs = []
    for i, meal in enumerate(meals):
        parts = meal.split("|", 1)
        meal_configs.append(
            {
                "meal_type": parts[0],
                "serving_line": parts[1] if len(parts) > 1 else parts[0],
                "sort_order": i,
            }
        )

    categories = form.getlist("categories") or None
    excluded_raw = form.get("excluded_items", "")
    excluded_items = [x.strip() for x in excluded_raw.split(",") if x.strip()] or None
    alert_str = form.get("alert_minutes", "")
    try:
        alert_minutes = int(alert_str) if alert_str else None
    except ValueError:
        alert_minutes = None
    show_as_busy = "show_as_busy" in form

    sub = Subscription(
        user_id=user.id,
        school_id=school_id,
        school_name=school_name,
        grade=form.get("grade", ""),
        meal_configs=meal_configs,
        display_name=form.get("display_name", ""),
        included_categories=categories,
        excluded_items=excluded_items,
        alert_minutes=alert_minutes,
        show_as_busy=show_as_busy,
    )
    db.add(sub)
    db.commit()

    return RedirectResponse(url=f"/subscriptions/{sub.id}", status_code=303)


@router.get("/subscriptions/{subscription_id}", response_class=HTMLResponse)
def subscription_detail(
    subscription_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(
        request,
        "subscription_detail.html",
        {
            "user": user,
            "sub": sub,
            "base_url": settings.base_url,
        },
    )


@router.post("/subscriptions/{subscription_id}/settings", response_class=HTMLResponse)
async def update_subscription_settings(
    subscription_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    form = await request.form()

    sub.display_name = form.get("display_name", sub.display_name)
    sub.grade = form.get("grade", sub.grade)

    categories = form.getlist("categories")
    sub.included_categories = categories or None

    excluded_raw = form.get("excluded_items", "")
    sub.excluded_items = [
        x.strip() for x in excluded_raw.split(",") if x.strip()
    ] or None

    alert_str = form.get("alert_minutes", "")
    try:
        sub.alert_minutes = int(alert_str) if alert_str else None
    except ValueError:
        sub.alert_minutes = None

    sub.show_as_busy = "show_as_busy" in form

    db.commit()
    return Response('<span style="color: green;">Saved!</span>')


@router.post(
    "/subscriptions/{subscription_id}/regenerate-token",
    response_class=HTMLResponse,
)
def regenerate_token_web(
    subscription_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.feed_token = uuid.uuid4()
    db.commit()
    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/subscriptions/{subscription_id}"},
    )


@router.get("/web/schools/options", response_class=HTMLResponse)
def school_options(q: str):
    """HTMX endpoint: returns <option> elements for the school select."""
    if not q.strip():
        return Response('<option value="">Enter a district code</option>')
    try:
        with SchoolCafeClient() as client:
            schools = client.search_schools(q.strip())
    except Exception:
        logger.exception("School search failed for query: %s", q.strip())
        return Response('<option value="">Error searching schools</option>')
    if not schools:
        return Response('<option value="">No schools found</option>')
    options = "".join(
        f'<option value="{escape(s.school_id)}" data-name="{escape(s.school_name)}">'
        f"{escape(s.school_name)}</option>"
        for s in schools
    )
    return Response(options)


@router.get("/subscriptions/{subscription_id}/preview", response_class=HTMLResponse)
def subscription_preview(
    subscription_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        return RedirectResponse(url="/dashboard")

    items = (
        db.query(MenuItem)
        .filter(MenuItem.subscription_id == sub.id)
        .order_by(MenuItem.menu_date, MenuItem.meal_type)
        .all()
    )

    # Apply same filters as the iCal feed
    if sub.included_categories:
        items = [i for i in items if i.category in sub.included_categories]
    if sub.excluded_items:
        excluded_lower = [e.lower() for e in sub.excluded_items if e.strip()]
        items = [
            i
            for i in items
            if not any(exc in i.item_name.lower() for exc in excluded_lower)
        ]

    # Group by date -> meal_type -> items
    grouped: dict = {}
    for item in items:
        date_str = item.menu_date.isoformat()
        grouped.setdefault(date_str, {}).setdefault(item.meal_type, []).append(item)

    return templates.TemplateResponse(
        request,
        "subscription_preview.html",
        {
            "user": user,
            "sub": sub,
            "grouped_items": grouped,
        },
    )
