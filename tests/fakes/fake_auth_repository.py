"""Fake auth repository for unit tests.

Split from fake_repositories.py to stay under RULE-04 line limit (400).
"""

from __future__ import annotations

import uuid

from narrare.auth.models import User
from tests.fakes._shared import CallRecord, _apply_setattr


class FakeAuthRepository:
    """
    In-memory fake for AuthRepositoryProtocol.

    Stores users keyed by email and by id.
    """

    def __init__(self) -> None:
        self._by_email: dict[str, User] = {}
        self._by_id: dict[uuid.UUID, User] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *users: User) -> None:
        for u in users:
            self._by_email[u.email.lower()] = u
            self._by_id[u.id] = u

    async def get_by_email(self, email: str) -> User | None:
        self.calls.append(CallRecord("get_by_email", kwargs={"email": email}))
        return self._by_email.get(email.lower())

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        self.calls.append(CallRecord("get_by_id", kwargs={"user_id": user_id}))
        return self._by_id.get(user_id)

    async def create(self, email: str, hashed_password: str, display_name: str = "") -> User:
        self.calls.append(
            CallRecord("create", kwargs={"email": email, "display_name": display_name})
        )
        user = User()
        _apply_setattr(
            user,
            {
                "id": uuid.uuid4(),
                "email": email.lower(),
                "hashed_password": hashed_password,
                "display_name": display_name,
                "is_active": True,
                "is_verified": False,
            },
        )
        self._by_email[user.email] = user
        self._by_id[user.id] = user
        return user

    async def set_verified(self, user_id: uuid.UUID) -> None:
        self.calls.append(CallRecord("set_verified", kwargs={"user_id": user_id}))
        user = self._by_id.get(user_id)
        if user:
            user.is_verified = True

    async def update_hashed_password(self, user_id: uuid.UUID, hashed_password: str) -> None:
        self.calls.append(CallRecord("update_hashed_password", kwargs={"user_id": user_id}))
        user = self._by_id.get(user_id)
        if user:
            user.hashed_password = hashed_password

    def assert_called_once(self, method: str) -> None:
        count = sum(1 for c in self.calls if c.method == method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)
