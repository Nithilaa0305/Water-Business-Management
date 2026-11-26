"""Audit service providing append-only activity logging."""

import json
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.database.models.operations import AuditLog
from app.utilities.logger import logger


class AuditService:
    @staticmethod
    def log_action(
        session: Session,
        action_type: str,
        entity_name: str,
        entity_id: Optional[int] = None,
        reference_no: Optional[str] = None,
        old_values: Optional[Any] = None,
        new_values: Optional[Any] = None,
        reason: Optional[str] = None,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
        role: Optional[str] = None
    ) -> AuditLog:
        """Create an immutable audit log record."""
        old_val_str = json.dumps(old_values, default=str) if old_values is not None else None
        new_val_str = json.dumps(new_values, default=str) if new_values is not None else None

        log_entry = AuditLog(
            user_id=user_id,
            user_name=user_name or "System",
            role=role or "SYSTEM",
            action_type=action_type,
            entity_name=entity_name,
            entity_id=entity_id,
            reference_no=reference_no,
            old_values=old_val_str,
            new_values=new_val_str,
            reason=reason
        )
        session.add(log_entry)
        logger.info(f"AUDIT [{action_type}] {entity_name} #{entity_id or ''} Ref:{reference_no or ''} by {user_name or 'System'}")
        return log_entry
