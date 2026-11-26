"""Authentication, user session management, lockout protection, and auto-login service."""

import os
import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.database.models.auth import User
from app.database.migrations.migration_manager import hash_password, verify_password
from app.config.constants import UserRole
from app.config.settings import DATA_DIR
from app.utilities.dates import now_colombo
from app.services.audit_service import AuditService
from app.utilities.logger import logger

SESSION_FILE = DATA_DIR / "session.json"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 5


class AuthService:
    _current_user: Optional[User] = None
    _screen_locked: bool = False

    @staticmethod
    def _check_user_lockout(user: User, now_dt) -> Tuple[bool, int]:
        """Check if user account is locked, handling naive/aware datetimes safely."""
        if not user.locked_until:
            return False, 0
        locked_dt = user.locked_until
        if hasattr(locked_dt, "tzinfo") and locked_dt.tzinfo is not None:
            locked_dt = locked_dt.replace(tzinfo=None)
        now_naive = now_dt.replace(tzinfo=None) if hasattr(now_dt, "tzinfo") and now_dt.tzinfo is not None else now_dt
        if locked_dt > now_naive:
            mins = max(1, int((locked_dt - now_naive).total_seconds() // 60))
            return True, mins
        return False, 0

    @classmethod
    def get_current_user(cls) -> Optional[User]:
        return cls._current_user

    @classmethod
    def set_current_user(cls, user: Optional[User]) -> None:
        cls._current_user = user

    @classmethod
    def is_authenticated(cls) -> bool:
        return cls._current_user is not None

    @classmethod
    def is_screen_locked(cls) -> bool:
        return cls._screen_locked

    @classmethod
    def lock_screen(cls) -> None:
        cls._screen_locked = True

    @classmethod
    def unlock_screen(cls, session: Session, pin_or_password: str) -> Tuple[bool, str]:
        """Unlock screen for current user using their PIN or password, or master owner credentials."""
        code = (pin_or_password or "").strip()
        if not code:
            return False, "Please enter your PIN or password."

        # Verify against current user first
        if cls._current_user:
            user = session.query(User).filter_by(id=cls._current_user.id, is_active=True).first()
            if user:
                if user.pin_hash and verify_password(code, user.pin_hash):
                    cls._screen_locked = False
                    return True, "Unlocked"
                if user.password_hash and verify_password(code, user.password_hash):
                    cls._screen_locked = False
                    return True, "Unlocked"

        # Allow any active OWNER or MANAGER credentials to unlock terminal
        masters = session.query(User).filter(
            User.role.in_([UserRole.OWNER.value, UserRole.MANAGER.value]),
            User.is_active == True
        ).all()
        for m in masters:
            if m.pin_hash and verify_password(code, m.pin_hash):
                cls._screen_locked = False
                cls._current_user = m
                return True, "Unlocked"
            if m.password_hash and verify_password(code, m.password_hash):
                cls._screen_locked = False
                cls._current_user = m
                return True, "Unlocked"

        return False, "Invalid PIN or password."

    @classmethod
    def logout(cls) -> None:
        """Alias for logout_user."""
        cls.logout_user()

    @classmethod
    def get_current_role(cls) -> str:
        if cls._current_user:
            return cls._current_user.role
        return UserRole.EMPLOYEE.value

    @classmethod
    def is_owner(cls) -> bool:
        return cls.get_current_role() == UserRole.OWNER.value

    @classmethod
    def is_manager_or_higher(cls) -> bool:
        return cls.get_current_role() in (UserRole.OWNER.value, UserRole.MANAGER.value)

    @staticmethod
    def verify_credentials(
        session: Session,
        username_or_pin: str,
        password: Optional[str] = None,
        remember_me: bool = False
    ) -> Tuple[bool, Optional[User], str]:
        """
        Authenticate user by username+password or PIN.
        Includes failed login lockout and automatic password upgrade to Argon2id.
        """
        now = now_colombo()

        if password is not None:
            user = session.query(User).filter_by(username=username_or_pin, is_active=True).first()
            if not user:
                return False, None, "User not found or inactive."

            # Check lockout
            is_locked, mins_left = AuthService._check_user_lockout(user, now)
            if is_locked:
                return False, None, f"Account is temporarily locked. Try again in {mins_left} minute(s)."

            if not verify_password(password, user.password_hash):
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                    session.commit()
                    return False, None, f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes."
                session.commit()
                return False, None, f"Invalid password. ({MAX_FAILED_ATTEMPTS - user.failed_login_attempts} attempts left)"

            # Successful password login: reset lockout
            user.failed_login_attempts = 0
            user.locked_until = None

            # Transparently upgrade legacy hash to Argon2id
            if user.password_hash and not user.password_hash.startswith("$argon2"):
                user.password_hash = hash_password(password)

        else:
            # PIN sign in
            all_users = session.query(User).filter_by(is_active=True).all()
            user = None
            for u in all_users:
                if u.pin_hash and verify_password(username_or_pin, u.pin_hash):
                    user = u
                    break

            if not user:
                return False, None, "Invalid PIN or inactive user."

            is_locked, mins_left = AuthService._check_user_lockout(user, now)
            if is_locked:
                return False, None, f"Account is temporarily locked. Try again in {mins_left} minute(s)."

            user.failed_login_attempts = 0
            user.locked_until = None

        user.last_login = now
        AuthService._current_user = user
        AuthService._screen_locked = False

        # Remember Me session persistence
        if remember_me:
            token = uuid.uuid4().hex
            user.remember_token = token
            AuthService._save_remember_session(user.id, token, user.username)

        session.commit()

        AuditService.log_action(
            session=session,
            action_type="SIGN_IN",
            entity_name="User",
            entity_id=user.id,
            user_id=user.id,
            user_name=user.full_name,
            role=user.role,
            reason="User signed in"
        )
        return True, user, "Success"

    @classmethod
    def try_auto_login(cls, session: Session) -> Tuple[bool, Optional[User], str]:
        """
        Attempt auto-login using saved session on this PC.
        Allows instant access without logging in every single time.
        """
        if not SESSION_FILE.exists():
            return False, None, "No active remembered session."

        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            user_id = data.get("user_id")
            token = data.get("token")
            if not user_id or not token:
                return False, None, "Invalid session data."

            user = session.query(User).filter_by(id=user_id, is_active=True).first()
            if not user or user.remember_token != token:
                cls.clear_remember_session()
                return False, None, "Session expired or invalid."

            # Check if locked
            now = now_colombo()
            is_locked, _ = cls._check_user_lockout(user, now)
            if is_locked:
                return False, None, "Account is currently locked."

            user.last_login = now
            cls._current_user = user
            cls._screen_locked = False
            session.commit()

            logger.info(f"Auto-login successful for user '{user.username}' ({user.full_name}).")
            return True, user, "Auto-login successful"
        except Exception as e:
            logger.warning(f"Auto-login failed: {e}")
            cls.clear_remember_session()
            return False, None, str(e)

    @classmethod
    def logout_user(cls) -> None:
        """Sign out current user and clear local remembered session."""
        cls._current_user = None
        cls._screen_locked = False
        cls.clear_remember_session()

    @staticmethod
    def _save_remember_session(user_id: int, token: str, username: str) -> None:
        try:
            SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump({"user_id": user_id, "token": token, "username": username}, f)
        except Exception as e:
            logger.warning(f"Could not save remember session: {e}")

    @staticmethod
    def clear_remember_session() -> None:
        try:
            if SESSION_FILE.exists():
                os.remove(SESSION_FILE)
        except Exception as e:
            logger.warning(f"Could not remove session file: {e}")

    @staticmethod
    def create_user(
        session: Session,
        username: str,
        full_name: str,
        password: str,
        role: str,
        pin: Optional[str] = None,
        created_by: Optional[User] = None
    ) -> User:
        """Create a new application user."""
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            raise ValueError(f"Username '{username}' already exists.")

        user = User(
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            pin_hash=hash_password(pin) if pin else None,
            role=role,
            is_active=True
        )
        session.add(user)
        session.flush()

        AuditService.log_action(
            session=session,
            action_type="USER_CREATE",
            entity_name="User",
            entity_id=user.id,
            new_values={"username": username, "role": role},
            user_id=created_by.id if created_by else None,
            user_name=created_by.full_name if created_by else "System",
            role=created_by.role if created_by else "OWNER"
        )
        return user
