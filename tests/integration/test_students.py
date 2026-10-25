"""Student CRUD integration tests."""

from app.constants import STUDENT_ACTIVE, STUDENT_INACTIVE
from app.extensions import db
from app.models import Student
from app.services import allocation_service

STUDENT_DATA = {
    "full_name": "Jane Doe",
    "email": "jane@test.example",
    "phone": "9000000001",
    "roll_number": "R9001",
    "course": "Computer Science",
    "academic_year": "1",
    "admission_date": "2026-01-05",
    "status": STUDENT_ACTIVE,
}


def test_create_student_persists(admin_client):
    resp = admin_client.post("/students/new", data=STUDENT_DATA)
    assert resp.status_code == 302
    student = db.session.execute(
        db.select(Student).where(Student.roll_number == "R9001")
    ).scalar_one()
    assert student.full_name == "Jane Doe"
    assert student.email == "jane@test.example"


def test_create_student_with_portal_login(admin_client):
    data = {**STUDENT_DATA, "create_login": "y", "password": "Secret123"}
    resp = admin_client.post("/students/new", data=data)
    assert resp.status_code == 302
    student = db.session.execute(
        db.select(Student).where(Student.roll_number == "R9001")
    ).scalar_one()
    assert student.user is not None
    assert student.user.check_password("Secret123")


def test_create_student_duplicate_email_rejected(admin_client, make_student):
    make_student(email="dupe@test.example")
    resp = admin_client.post("/students/new", data={**STUDENT_DATA, "email": "dupe@test.example"})
    assert resp.status_code == 200
    assert (
        db.session.execute(
            db.select(Student).where(Student.roll_number == "R9001")
        ).scalar_one_or_none()
        is None
    )


def test_list_and_view_student(admin_client, make_student):
    student = make_student()
    assert admin_client.get("/students/").status_code == 200
    assert admin_client.get(f"/students/{student.id}").status_code == 200


def test_view_missing_student_returns_404(admin_client):
    assert admin_client.get("/students/999999").status_code == 404


def test_edit_student(admin_client, make_student):
    student = make_student()
    data = {
        **STUDENT_DATA,
        "full_name": "Jane Updated",
        "roll_number": student.roll_number,
        "email": student.email,
        "admission_date": student.admission_date.isoformat(),
    }
    resp = admin_client.post(f"/students/{student.id}/edit", data=data)
    assert resp.status_code == 302
    db.session.refresh(student)
    assert student.full_name == "Jane Updated"


def test_deactivating_student_releases_room(admin_client, make_student, room):
    student = make_student()
    allocation_service.allocate_bed(student)
    assert room.available_beds == room.capacity - 1

    resp = admin_client.post(f"/students/{student.id}/status", data={"status": STUDENT_INACTIVE})
    assert resp.status_code == 302
    db.session.refresh(student)
    assert student.status == STUDENT_INACTIVE
    assert student.current_allocation is None
    assert room.available_beds == room.capacity


def test_deactivating_student_disables_login(admin_client, make_student):
    student = make_student(with_login=True, email="stu@test.example", password="StudentPass1")
    assert student.user.is_active
    admin_client.post(f"/students/{student.id}/status", data={"status": STUDENT_INACTIVE})
    db.session.refresh(student.user)
    assert student.user.is_active is False


def test_invalid_status_change_is_ignored(admin_client, make_student):
    student = make_student()
    admin_client.post(f"/students/{student.id}/status", data={"status": "bogus"})
    db.session.refresh(student)
    assert student.status == STUDENT_ACTIVE
