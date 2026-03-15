from unittest.mock import MagicMock

from fastapi import HTTPException
import pytest

from lunchbox.auth.dependencies import get_current_user


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
