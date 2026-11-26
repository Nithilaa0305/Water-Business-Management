"""Unit tests for Argon2id hashing, lockout protection, auto-login, and screen lock."""

import pytest
from app.services.auth_service import AuthService
from app.database.migrations.migration_manager import hash_password, verify_password
from app.database.models.auth import User


def test_argon2id_hashing_and_legacy_compatibility():
    # 1. New hash is Argon2id
    h = hash_password("secret123")
    assert h.startswith("$argon2id$")
    assert verify_password("secret123", h) is True
    assert verify_password("wrongpassword", h) is False

    # 2. Backwards compatible with legacy SHA-256
    import hashlib
    salt = "WaterBusinessSalt2026"
    legacy_h = hashlib.sha256(f"{salt}admin123".encode("utf-8")).hexdigest()
    assert verify_password("admin123", legacy_h) is True
    assert verify_password("wrong", legacy_h) is False


def test_account_lockout_after_failed_attempts(db_session):
    u = AuthService.create_user(
        session=db_session,
        username="cashier_test",
        full_name="Test Cashier",
        password="password123",
        role="EMPLOYEE",
        pin="5566"
    )
    db_session.commit()

    # 4 failed attempts -> still active
    for _ in range(4):
        ok, user, msg = AuthService.verify_credentials(db_session, "cashier_test", "wrong_pass")
        assert ok is False

    # 5th failed attempt -> locks account
    ok, user, msg = AuthService.verify_credentials(db_session, "cashier_test", "wrong_pass")
    assert ok is False
    assert "locked" in msg.lower()

    # Subsequent attempt rejected because of lock
    ok, user, msg = AuthService.verify_credentials(db_session, "cashier_test", "password123")
    assert ok is False
    assert "locked" in msg.lower()


def test_auto_login_and_screen_lock(db_session):
    owner = db_session.query(User).filter_by(role="OWNER").first()
    assert owner is not None

    # Sign in with remember_me=True
    ok, user, msg = AuthService.verify_credentials(
        session=db_session,
        username_or_pin="admin",
        password="admin123",
        remember_me=True
    )
    assert ok is True
    assert AuthService.is_authenticated() is True

    # Test try_auto_login
    AuthService._current_user = None
    assert AuthService.is_authenticated() is False
    ok_auto, user_auto, _ = AuthService.try_auto_login(db_session)
    assert ok_auto is True
    assert user_auto.id == owner.id

    # Test screen lock and PIN unlock
    AuthService.lock_screen()
    assert AuthService.is_screen_locked() is True
    unlocked, _ = AuthService.unlock_screen(db_session, "1234")  # Default PIN
    assert unlocked is True
    assert AuthService.is_screen_locked() is False

    # Clear session on logout
    AuthService.logout_user()
    assert AuthService.is_authenticated() is False
