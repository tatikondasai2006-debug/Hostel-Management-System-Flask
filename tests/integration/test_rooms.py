"""Hostel and room management integration tests."""

from app.constants import ROOM_AVAILABLE, ROOM_MAINTENANCE
from app.extensions import db
from app.models import Hostel, Room
from app.services import allocation_service

ROOM_DATA = {
    "room_number": "B-1",
    "floor": 1,
    "room_type": "double",
    "capacity": 2,
    "base_fee": "4500.00",
    "status": ROOM_AVAILABLE,
}


def test_create_hostel(admin_client):
    resp = admin_client.post("/hostels/new", data={"name": "North Block"})
    assert resp.status_code == 302
    assert db.session.execute(db.select(Hostel).where(Hostel.name == "North Block")).scalar_one()


def test_duplicate_hostel_name_rejected(admin_client, hostel):
    resp = admin_client.post("/hostels/new", data={"name": hostel.name})
    assert resp.status_code == 200


def test_create_room(admin_client, hostel):
    resp = admin_client.post("/rooms/new", data={**ROOM_DATA, "hostel_id": hostel.id})
    assert resp.status_code == 302
    room = db.session.execute(db.select(Room).where(Room.room_number == "B-1")).scalar_one()
    assert room.capacity == 2
    assert str(room.base_fee) == "4500.00"


def test_create_room_without_hostel_redirects(admin_client):
    resp = admin_client.post("/rooms/new", data={**ROOM_DATA, "hostel_id": 1})
    assert resp.status_code == 302
    assert "/hostels/new" in resp.headers["Location"]


def test_duplicate_room_number_in_hostel_rejected(admin_client, hostel, room):
    resp = admin_client.post(
        "/rooms/new",
        data={**ROOM_DATA, "hostel_id": hostel.id, "room_number": room.room_number},
    )
    assert resp.status_code == 200


def test_change_room_status(admin_client, room):
    resp = admin_client.post(f"/rooms/{room.id}/status", data={"status": ROOM_MAINTENANCE})
    assert resp.status_code == 302
    db.session.refresh(room)
    assert room.status == ROOM_MAINTENANCE


def test_room_status_affects_availability_for_allocation(admin_client, room, make_student):
    admin_client.post(f"/rooms/{room.id}/status", data={"status": ROOM_MAINTENANCE})
    student = make_student()
    try:
        allocation_service.allocate_bed(student)
    except allocation_service.NoCapacityError:
        pass
    else:
        raise AssertionError("A maintenance room must not accept allocations")


def test_delete_room_without_history(admin_client, hostel, make_room):
    room = make_room(hostel, number="DEL-1")
    resp = admin_client.post(f"/rooms/{room.id}/delete")
    assert resp.status_code == 302
    assert db.session.get(Room, room.id) is None


def test_delete_room_with_history_blocked(admin_client, room, make_student):
    student = make_student()
    allocation_service.allocate_bed(student)
    resp = admin_client.post(f"/rooms/{room.id}/delete")
    assert resp.status_code == 302
    assert db.session.get(Room, room.id) is not None


def test_view_room(admin_client, room):
    assert admin_client.get(f"/rooms/{room.id}").status_code == 200
