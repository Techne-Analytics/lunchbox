from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()


def _register_oauth():
    """Register Google OAuth client. Skips if client_id not configured."""
    if settings.google_client_id:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=(
                "https://accounts.google.com/.well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid email profile"},
        )


_register_oauth()


@router.get("/login")
async def login(request: Request):
    redirect_uri = f"{settings.base_url}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})

    google_id = userinfo.get("sub")
    if not google_id:
        return RedirectResponse(url="/?error=auth_failed")

    # Upsert user — handle race condition on concurrent first-login
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = User(
            google_id=google_id,
            email=userinfo.get("email", ""),
            name=userinfo.get("name", ""),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(User.google_id == google_id).first()
    else:
        user.email = userinfo.get("email", user.email)
        user.name = userinfo.get("name", user.name)
        db.commit()

    db.refresh(user)

    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")
