"""Authentication flow integration tests."""

from app.extensions import db
from app.models import Student

SIGNUP_DATA = {
    "full_name": "New Student",
    "email": "newbie@test.example",
    "phone": "9000000009",
    "roll_number": "R9009",
    "course": "Physics",
    "academic_year": "1",
    "password": "StudentPass9",
    "confirm_password": "StudentPass9",
}


def test_login_page_renders(client):
    assert client.get("/auth/login").status_code == 200


def test_signup_page_renders(client):
    assert client.get("/auth/signup").status_code == 200


def test_login_redirects_admin_to_dashboard(client, admin_user):
    resp = client.post(
        "/auth/login",
        data={"email": "admin@test.example", "password": "AdminPass123"},
    )
    assert resp.status_code == 302
    assert "/admin" in resp.headers["Location"]


def test_login_invalid_password_shows_generic_error(client, admin_user):
    resp = client.post(
        "/auth/login",
        data={"email": "admin@test.example", "password": "definitely-wrong"},
    )
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data


def test_login_unknown_email_shows_generic_error(client):
    resp = client.post(
        "/auth/login",
        data={"email": "ghost@test.example", "password": "whatever123"},
    )
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data


def test_logout_invalidates_session(client, admin_client):
    assert admin_client.post("/auth/logout").status_code == 302
    # Admin area now redirects to the login page.
    resp = admin_client.get("/admin/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_signup_creates_student_and_logs_in(client):
    resp = client.post("/auth/signup", data=SIGNUP_DATA)
    assert resp.status_code == 302
    assert "/portal" in resp.headers["Location"]
    assert client.get("/portal/").status_code == 200

    student = db.session.execute(
        db.select(Student).where(Student.roll_number == "R9009")
    ).scalar_one()
    assert student.full_name == "New Student"
    assert student.user is not None


def test_signup_duplicate_email_returns_409(client, make_student):
    existing = make_student()
    data = {**SIGNUP_DATA, "email": existing.email, "roll_number": "UNIQUE99"}
    assert client.post("/auth/signup", data=data).status_code == 409


def test_signup_duplicate_roll_returns_409(client, make_student):
    existing = make_student()
    data = {**SIGNUP_DATA, "email": "unique99@test.example", "roll_number": existing.roll_number}
    assert client.post("/auth/signup", data=data).status_code == 409


def test_signup_weak_password_rejected(client):
    data = {**SIGNUP_DATA, "password": "short", "confirm_password": "short"}
    resp = client.post("/auth/signup", data=data)
    assert resp.status_code == 200
    student = db.session.execute(
        db.select(Student).where(Student.roll_number == "R9009")
    ).scalar_one_or_none()
    assert student is None


def test_healthz_reports_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
