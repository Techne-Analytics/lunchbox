from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import MenuItem, Subscription, User
from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(tags=["web"])
_here = Path(__file__).parent
templates = Jinja2Templates(directory=str(_here / "templates"))


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(
        "landing.html", {"request": request, "user": None}
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscriptions = db.query(Subscription).filter(Subscription.user_id == user.id).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "subscriptions": subscriptions,
            "base_url": settings.base_url,
        },
    )


@router.get("/subscriptions/new", response_class=HTMLResponse)
def new_subscription(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "subscription_new.html", {"request": request, "user": user}
    )


@router.post("/subscriptions/create")
async def create_subscription_web(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    school_id = form.get("school_id", "")
    # Look up school name from the SchoolCafe API
    school_name = school_id
    try:
        with SchoolCafeClient() as client:
            q = form.get("q", "")
            if q:
                schools = client.search_schools(q)
                for s in schools:
                    if s.school_id == school_id:
                        school_name = s.school_name
                        break
    except Exception:
        pass

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
    alert_minutes = int(alert_str) if alert_str else None
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
        "subscription_detail.html",
        {
            "request": request,
            "user": user,
            "sub": sub,
            "base_url": settings.base_url,
        },
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
        return Response('<option value="">Error searching schools</option>')
    if not schools:
        return Response('<option value="">No schools found</option>')
    options = "".join(
        f'<option value="{s.school_id}">{s.school_name}</option>' for s in schools
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
        excluded_lower = {e.lower() for e in sub.excluded_items}
        items = [i for i in items if i.item_name.lower() not in excluded_lower]

    # Group by date -> meal_type -> items
    grouped: dict = {}
    for item in items:
        date_str = item.menu_date.isoformat()
        grouped.setdefault(date_str, {}).setdefault(item.meal_type, []).append(item)

    return templates.TemplateResponse(
        "subscription_preview.html",
        {
            "request": request,
            "user": user,
            "sub": sub,
            "grouped_items": grouped,
        },
    )
