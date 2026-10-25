"""Authentication model."""

from __future__ import annotations

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.constants import ROLE_ADMIN, ROLE_STUDENT
from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


class User(UserMixin, TimestampMixin, ReprMixin, db.Model):
    """An authenticated account (administrator or student)."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    student = db.relationship(
        "Student", back_populates="user", uselist=False, foreign_keys="Student.user_id"
    )

    __table_args__ = (
        db.CheckConstraint("role IN ('admin', 'student')", name="ck_users_role_valid"),
        db.Index("ix_users_role_active", "role", "is_active"),
    )

    # -- password helpers --------------------------------------------------
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # -- role helpers ------------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_student(self) -> bool:
        return self.role == ROLE_STUDENT

    @property
    def display_name(self) -> str:
        if self.student and self.student.full_name:
            return self.student.full_name
        return self.email
