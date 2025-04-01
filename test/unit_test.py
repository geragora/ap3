from unittest.mock import AsyncMock
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from main import generate_short_code
import string
from db import Link, Base
from database import get_async_session


@pytest.fixture(scope="function")
def mock_db_session():
    mock_session = MagicMock()

    mock_session.execute.return_value.scalars.return_value.first.return_value = Link(
        short_code="myshort1", original_url="https://example.com", user_id=1
    )

    yield mock_session


@pytest.fixture(scope="function")
async def mock_redis_client():
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value="https://example.com")
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=True)
    yield mock_redis


@pytest.mark.asyncio
async def test_shorten_url(mock_db_session, mock_redis_client):
    client = TestClient(app)
    sh = 'sdf33243'
    with patch("main.get_async_session", return_value=mock_db_session):
        data = {
            "original_url": "https://example.com",
            "custom_alias": f"{sh}"
        }

        response = client.post("/links/shorten", json=data)

    assert response.status_code == 200
    assert "short_url" in response.json()
    assert response.json()["short_url"] == f"http://127.0.0.1:8000/links/{sh}"


def test_generate_short_code_default_length():
    code = generate_short_code()
    assert len(code) == 6
    assert all(c in string.ascii_letters + string.digits for c in code)


def test_generate_short_code_custom_length():
    length = 10
    code = generate_short_code(length)
    assert len(code) == length
    assert all(c in string.ascii_letters + string.digits for c in code)


def test_generate_short_code_randomness():
    codes = {generate_short_code() for _ in range(1000)}
    assert len(codes) == 1000


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False})
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine)


@pytest.fixture(scope="function")
def client():
    return TestClient(app)


@pytest.fixture(scope="function")
async def access_token(client):
    user_data = {
        "email": "testuser@example.com",
        "password": "password123",
    }

    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 201

    login_data = {
        "username": user_data["email"],
        "password": user_data["password"]}
    login_response = client.post("/auth/jwt/login", data=login_data)
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return token


@pytest.fixture(scope="function")
def db_session():
    session = TestingSessionLocal()

    Base.metadata.create_all(bind=engine)

    yield session

    Base.metadata.drop_all(bind=engine)
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    app.dependency_overrides[get_async_session] = lambda: db_session
    with TestClient(app) as client:
        yield client


def test_update_short_link_unauthorized(client):
    short_code = "short1"
    updated_url = "https://newexample.com"

    response = client.put(
        f"/links/{short_code}",
        json={
            "original_url": updated_url})

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


def test_delete_short_link_unauthorized(client):
    short_code = "short1"

    response = client.delete(f"/links/{short_code}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"
