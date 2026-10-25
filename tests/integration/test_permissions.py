"""Authorization boundary tests (role separation)."""

import pytest


def test_anonymous_admin_area_redirects_to_login(client):
    resp = client.get("/students/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_anonymous_portal_redirects_to_login(client):
    resp = client.get("/portal/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


@pytest.fixture
def student_client(client, make_student):
    make_student(with_login=True, email="stu@test.example", password="StudentPass1")
    client.post(
        "/auth/login",
        data={"email": "stu@test.example", "password": "StudentPass1"},
    )
    return client


def test_student_denied_admin_area(student_client):
    assert student_client.get("/students/").status_code == 403
    assert student_client.get("/rooms/").status_code == 403
    assert student_client.get("/fees/").status_code == 403
    assert student_client.get("/payments/").status_code == 403
    assert student_client.get("/allocations/").status_code == 403
    assert student_client.get("/admin/").status_code == 403


def test_student_can_access_portal(student_client):
    assert student_client.get("/portal/").status_code == 200
    assert student_client.get("/portal/profile").status_code == 200
    assert student_client.get("/portal/fees").status_code == 200
    assert student_client.get("/portal/payments").status_code == 200


def test_admin_denied_student_portal(admin_client):
    assert admin_client.get("/portal/").status_code == 403


def test_admin_can_access_admin_area(admin_client):
    assert admin_client.get("/admin/").status_code == 200
    assert admin_client.get("/students/").status_code == 200
    assert admin_client.get("/rooms/").status_code == 200
