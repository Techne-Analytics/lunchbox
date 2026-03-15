import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lunchbox.auth.dependencies import get_current_user
from lunchbox.models import User
from tests.factories import create_user


def test_login_redirects_to_google(client):
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "accounts.google.com" in response.headers.get("location", "")


def test_unauthenticated_raises_401():
    request = MagicMock()
    request.session = {}
    db = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request, db)
    assert exc_info.value.status_code == 401


def test_logout_clears_session(client):
    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers.get("location") == "/"


def test_get_current_user_deleted_from_db():
    """Valid session but user row gone -> 401."""
    request = MagicMock()
    request.session = {"user_id": str(uuid.uuid4())}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request, db)
    assert exc_info.value.status_code == 401


def test_callback_creates_new_user(client, db):
    """OAuth callback creates a new User and sets session."""
    mock_token = {
        "userinfo": {
            "sub": "new-google-id-123",
            "email": "new@example.com",
            "name": "New User",
        }
    }

    with patch("lunchbox.auth.router.oauth") as mock_oauth:
        mock_oauth.google.authorize_access_token = AsyncMock(return_value=mock_token)
        response = client.get("/auth/callback", follow_redirects=False)

    assert response.status_code in (302, 307)
    user = db.query(User).filter(User.google_id == "new-google-id-123").first()
    assert user is not None
    assert user.email == "new@example.com"


def test_callback_updates_returning_user(client, db):
    """Returning user gets email/name updated."""
    existing = create_user(
        db, google_id="returning-123", email="old@example.com", name="Old"
    )
    db.commit()

    mock_token = {
        "userinfo": {
            "sub": "returning-123",
            "email": "new@example.com",
            "name": "New Name",
        }
    }

    with patch("lunchbox.auth.router.oauth") as mock_oauth:
        mock_oauth.google.authorize_access_token = AsyncMock(return_value=mock_token)
        client.get("/auth/callback", follow_redirects=False)

    db.refresh(existing)
    assert existing.email == "new@example.com"
    assert existing.name == "New Name"


def test_callback_missing_google_id(client):
    """Missing 'sub' in userinfo redirects with error."""
    mock_token = {"userinfo": {}}

    with patch("lunchbox.auth.router.oauth") as mock_oauth:
        mock_oauth.google.authorize_access_token = AsyncMock(return_value=mock_token)
        response = client.get("/auth/callback", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "error" in response.headers.get("location", "")
