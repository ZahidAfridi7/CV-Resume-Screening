"""Integration tests for auth: register, login, refresh, logout, protected route."""
import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_register_and_login(client: AsyncClient):
    """Register a user, then login; both return access_token and refresh_token."""
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    password = "securepassword123"

    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"
    assert data.get("refresh_token") is not None

    r2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert "access_token" in data2
    assert data2.get("refresh_token") is not None


async def test_login_invalid_password(client: AsyncClient):
    """Login with wrong password returns 401."""
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "right"})

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong"},
    )
    assert r.status_code == 401


async def test_refresh_token(client: AsyncClient):
    """Refresh token returns new access_token and refresh_token."""
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "pass123"},
    )
    assert reg.status_code == 200
    refresh_token = reg.json()["refresh_token"]

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data.get("refresh_token") is not None


async def test_refresh_invalid_token(client: AsyncClient):
    """Invalid refresh token returns 401."""
    r = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.jwt.here"},
    )
    assert r.status_code == 401


async def test_protected_route_without_token(client: AsyncClient):
    """Calling a protected route without Bearer token returns 401."""
    r = await client.get("/api/v1/job-descriptions")
    assert r.status_code == 401


async def test_protected_route_with_token(client: AsyncClient):
    """Calling a protected route with valid token returns 200."""
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "pass123"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]

    r = await client.get(
        "/api/v1/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "items" in r.json()


async def test_logout(client: AsyncClient):
    """Logout revokes the token (when Redis available); endpoint returns 200."""
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "pass123"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]

    r = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "Logged out" in r.json().get("detail", "")
