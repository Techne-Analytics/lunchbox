from datetime import date

from tests.factories import create_menu_item, create_subscription, create_user


def test_landing_unauthenticated(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200


def test_landing_with_session_redirects(client, db):
    """Landing page checks request.session['user_id'] directly (not get_current_user).
    Use the auth callback to establish a real session, then verify redirect."""
    from unittest.mock import AsyncMock, patch

    mock_token = {
        "userinfo": {"sub": "landing-test-id", "email": "t@t.com", "name": "T"},
    }

    with patch("lunchbox.auth.router.oauth") as mock_oauth:
        mock_oauth.google.authorize_access_token = AsyncMock(return_value=mock_token)
        client.get("/auth/callback", follow_redirects=False)

    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/dashboard" in response.headers.get("location", "")


def test_dashboard_authenticated(authenticated_client, db):
    client, user = authenticated_client
    create_subscription(db, user, display_name="My Sub")
    db.commit()

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "My Sub" in response.text


def test_dashboard_unauthenticated(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code in (401, 302, 307)


def test_new_subscription_form(authenticated_client):
    client, _ = authenticated_client
    response = client.get("/subscriptions/new")
    assert response.status_code == 200


def test_subscription_detail_owner(authenticated_client, db):
    client, user = authenticated_client
    sub = create_subscription(db, user)
    db.commit()

    response = client.get(f"/subscriptions/{sub.id}")
    assert response.status_code == 200


def test_subscription_detail_other_user_redirects(authenticated_client, db):
    """Accessing another user's subscription redirects to dashboard."""
    client, _ = authenticated_client
    other = create_user(db, google_id="other-web")
    other_sub = create_subscription(db, other)
    db.commit()

    response = client.get(f"/subscriptions/{other_sub.id}", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/dashboard" in response.headers.get("location", "")


def test_subscription_preview(authenticated_client, db):
    client, user = authenticated_client
    sub = create_subscription(db, user)
    create_menu_item(db, sub, menu_date=date(2026, 3, 16), item_name="Tacos")
    db.commit()

    response = client.get(f"/subscriptions/{sub.id}/preview")
    assert response.status_code == 200
    assert "Tacos" in response.text
