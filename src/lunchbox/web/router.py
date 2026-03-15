from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import MenuItem, Subscription, User

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
