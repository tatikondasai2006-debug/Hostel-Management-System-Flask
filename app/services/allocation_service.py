"""Concurrency-safe room allocation.

Strategy
--------
Bed allocation is performed inside a single database transaction:

1. Candidate rooms are read ordered deterministically (requested room type
   first, then room number).
2. Each candidate room row is locked with ``SELECT ... FOR UPDATE SKIP
   LOCKED``.  ``SKIP LOCKED`` means a competing transaction never waits on a
   room another transaction is already filling; it simply moves on to the next
   candidate.  This removes the classic "check then insert" race and avoids
   deadlocks caused by lock ordering.
3. While holding the room lock, occupancy is *recomputed inside the
   transaction* and the lowest free bed index is chosen.
4. The allocation row is flushed.  Two PostgreSQL partial unique indexes
   (``uq_active_allocation_per_student`` and ``uq_active_allocation_per_bed``)
   and a ``BEFORE INSERT`` trigger that compares the active count against room
   capacity form the final integrity safeguard at the database level.
5. Transient PostgreSQL errors (serialization failure ``40001``, deadlock
   ``40P01``, lock-not-available ``55P03``) and unique-index races ``23505``
   are retried a bounded number of times with exponential backoff.

The service works on SQLite too (unit tests): SQLite ignores ``FOR UPDATE``
and relies on the unique indexes, so SQLite is *not* used as proof of
PostgreSQL concurrency safety.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from app.constants import (
    ALLOCATION_ACTIVE,
    ALLOCATION_RELEASED,
    ROOM_AVAILABLE,
    STUDENT_ACTIVE,
)
from app.extensions import db
from app.models import Room, RoomAllocation, Student

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
RETRY_DELAY_SECONDS = 0.05

# PostgreSQL SQLSTATEs that are safe to retry.
_TRANSIENT_SQLSTATES = {
    "40001",  # serialization_failure
    "40P01",  # deadlock_detected
    "55P03",  # lock_not_available
    "23505",  # unique_violation (partial unique index race)
}


class AllocationError(Exception):
    """Raised when an allocation cannot be performed for a business reason."""


class NoCapacityError(AllocationError):
    """Raised when no eligible room with a free bed exists."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _sqlstate(exc: DBAPIError) -> str | None:
    return getattr(getattr(exc, "orig", None), "pgcode", None)


def _is_transient(exc: DBAPIError) -> bool:
    code = _sqlstate(exc)
    if code and code in _TRANSIENT_SQLSTATES:
        return True
    # SQLite has no SQLSTATE; unique constraint races surface as IntegrityError.
    return isinstance(exc, IntegrityError)


def candidate_room_ids(room_type: str | None = None) -> list[int]:
    """Return eligible room ids ordered deterministically.

    Rooms matching ``room_type`` are preferred; ties break on room number so
    the outcome is reproducible.
    """
    stmt = select(Room.id, Room.room_number, Room.room_type).where(Room.status == ROOM_AVAILABLE)
    if room_type:
        stmt = stmt.order_by((Room.room_type != room_type), Room.room_number, Room.id)
    else:
        stmt = stmt.order_by(Room.room_number, Room.id)
    return [row.id for row in db.session.execute(stmt).all()]


def _lock_room(room_id: int) -> Room | None:
    stmt = (
        select(Room)
        .where(Room.id == room_id, Room.status == ROOM_AVAILABLE)
        .with_for_update(skip_locked=True)
    )
    return db.session.execute(stmt).scalar_one_or_none()


def _active_count(room_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(RoomAllocation)
        .where(
            RoomAllocation.room_id == room_id,
            RoomAllocation.status == ALLOCATION_ACTIVE,
        )
    )
    return int(db.session.execute(stmt).scalar_one())


def _used_bed_indices(room_id: int) -> set[int]:
    stmt = select(RoomAllocation.bed_index).where(
        RoomAllocation.room_id == room_id,
        RoomAllocation.status == ALLOCATION_ACTIVE,
    )
    return set(db.session.execute(stmt).scalars().all())


def _lowest_free_bed(room: Room) -> int | None:
    used = _used_bed_indices(room.id)
    for index in range(1, room.capacity + 1):
        if index not in used:
            return index
    return None


def _active_allocation_for(student_id: int) -> RoomAllocation | None:
    return db.session.execute(
        select(RoomAllocation).where(
            RoomAllocation.student_id == student_id,
            RoomAllocation.status == ALLOCATION_ACTIVE,
        )
    ).scalar_one_or_none()


def _attempt_allocation(
    student: Student,
    room_type: str | None,
    allocated_by,
    notes: str | None,
    preferred_room_id: int | None = None,
) -> RoomAllocation | None:
    """One allocation attempt. Returns a flushed allocation or ``None``."""
    if student.status != STUDENT_ACTIVE:
        raise AllocationError("Only active students can be allocated a room.")
    if _active_allocation_for(student.id) is not None:
        raise AllocationError("Student already has an active room allocation.")

    ids = candidate_room_ids(room_type)
    if preferred_room_id is not None:
        ids = sorted(ids, key=lambda rid: (rid != preferred_room_id,))

    for room_id in ids:
        room = _lock_room(room_id)
        if room is None:  # locked by a competing transaction or now unavailable
            continue
        if _active_count(room.id) >= room.capacity:
            continue
        bed = _lowest_free_bed(room)
        if bed is None:
            continue
        allocation = RoomAllocation(
            student_id=student.id,
            room_id=room.id,
            bed_index=bed,
            status=ALLOCATION_ACTIVE,
            allocated_at=_utcnow(),
            allocated_by_id=getattr(allocated_by, "id", None),
            notes=notes,
        )
        db.session.add(allocation)
        db.session.flush()
        return allocation
    return None


def allocate_bed(
    student: Student,
    room_type: str | None = None,
    allocated_by=None,
    notes: str | None = None,
    preferred_room_id: int | None = None,
) -> RoomAllocation:
    """Allocate the lowest available bed to ``student`` atomically.

    Raises :class:`AllocationError` / :class:`NoCapacityError` on failure;
    the transaction is always rolled back first so no partial assignment
    remains.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            allocation = _attempt_allocation(
                student, room_type, allocated_by, notes, preferred_room_id
            )
            if allocation is None:
                db.session.rollback()
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (2**attempt))
                    continue
                raise NoCapacityError("No room with an available bed matches the request.")
            db.session.commit()
            return allocation
        except AllocationError:
            db.session.rollback()
            raise
        except (OperationalError, IntegrityError) as exc:
            db.session.rollback()
            if not _is_transient(exc):
                raise
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS * (2**attempt))
            logger.debug("Retrying allocation after transient error: %s", exc)
        except DBAPIError as exc:
            db.session.rollback()
            if not _is_transient(exc):
                raise
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS * (2**attempt))

    raise NoCapacityError(
        "Could not allocate a bed after repeated contention. Please try again. ({})".format(
            type(last_exc).__name__ if last_exc else "n/a"
        )
    )


def release_allocation(
    allocation: RoomAllocation,
    reason: str | None = None,
    released_by=None,
    commit: bool = True,
) -> RoomAllocation:
    """Release an active allocation (idempotent)."""
    if allocation.status != ALLOCATION_ACTIVE:
        return allocation
    allocation.status = ALLOCATION_RELEASED
    allocation.released_at = _utcnow()
    allocation.release_reason = reason
    if released_by is not None:
        allocation.notes = (
            f"{allocation.notes or ''}\n[released by admin #{released_by.id}]".strip()
        )
    db.session.flush()
    if commit:
        db.session.commit()
    return allocation


def transfer_student(
    student: Student,
    new_room_id: int,
    allocated_by=None,
    notes: str | None = None,
) -> RoomAllocation:
    """Move a student to another room atomically (release + allocate)."""
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            target = _lock_room(new_room_id)
            if target is None:
                db.session.rollback()
                raise AllocationError("The selected room is not available.")

            current = _active_allocation_for(student.id)
            if current is not None and current.room_id == target.id:
                db.session.rollback()
                raise AllocationError("The student is already assigned to that room.")

            if _active_count(target.id) >= target.capacity:
                db.session.rollback()
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (2**attempt))
                    continue
                raise NoCapacityError("The selected room is already full.")

            if current is not None:
                current.status = ALLOCATION_RELEASED
                current.released_at = _utcnow()
                current.release_reason = "transfer"
                db.session.flush()  # frees the student's active-allocation slot

            bed = _lowest_free_bed(target)
            if bed is None:
                db.session.rollback()
                raise NoCapacityError("The selected room is already full.")

            allocation = RoomAllocation(
                student_id=student.id,
                room_id=target.id,
                bed_index=bed,
                status=ALLOCATION_ACTIVE,
                allocated_at=_utcnow(),
                allocated_by_id=getattr(allocated_by, "id", None),
                notes=notes,
            )
            db.session.add(allocation)
            db.session.flush()
            db.session.commit()
            return allocation
        except AllocationError:
            db.session.rollback()
            raise
        except (OperationalError, IntegrityError) as exc:
            db.session.rollback()
            if not _is_transient(exc):
                raise
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS * (2**attempt))
        except DBAPIError as exc:
            db.session.rollback()
            if not _is_transient(exc):
                raise
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS * (2**attempt))

    raise NoCapacityError(
        "Could not transfer the student after repeated contention. Please try again. ({})".format(
            type(last_exc).__name__ if last_exc else "n/a"
        )
    )


def can_reduce_capacity(room: Room, new_capacity: int) -> bool:
    """A room's capacity must never drop below its current occupancy."""
    return new_capacity >= _active_count(room.id)
