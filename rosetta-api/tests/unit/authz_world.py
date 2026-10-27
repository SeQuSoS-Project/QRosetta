"""The whole API (main.app) on an in-memory database, with accounts made directly in it, for the
authorization and token tests."""
import contextlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.models as models
from db.database import Base, get_db
from services.security import access_token_for, get_password_hash

PASSWORD = "correct horse battery"
_HASH = get_password_hash(PASSWORD)


class World:
    """An app client and its database session factory."""

    def __init__(self, client, session):
        self.client = client
        self.session = session

    def user(self, email=None, *, active=True, created_at=None) -> int:
        with self.session() as db:
            user = models.User(email=email or f"{uuid.uuid4().hex[:12]}@example.org", hashed_password=_HASH,
                               auth_provider="local", is_active=active,
                               created_at=created_at or datetime.now(timezone.utc) - timedelta(minutes=5))
            db.add(user)
            db.commit()
            return user.id

    def token(self, user_id) -> str:
        with self.session() as db:
            user = db.get(models.User, user_id)
            return access_token_for(user, timedelta(minutes=30))

    def headers(self, user_id) -> dict:
        return {"Authorization": f"Bearer {self.token(user_id)}"}

    def set_active(self, user_id, active):
        with self.session() as db:
            db.get(models.User, user_id).is_active = active
            db.commit()

    def get_user(self, user_id):
        with self.session() as db:
            user = db.get(models.User, user_id)
            if user is not None:
                db.expunge(user)
            return user


@contextlib.contextmanager
def world(tmp_path, monkeypatch):
    """main.app with get_db bound to a fresh in-memory database and reports under tmp_path."""
    import main
    import services.storage as storage
    monkeypatch.setattr(storage, "MOCK_S3_DIR", str(tmp_path / "reports"))
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = _get_db
    try:
        yield World(TestClient(main.app, raise_server_exceptions=False), session)
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        engine.dispose()
