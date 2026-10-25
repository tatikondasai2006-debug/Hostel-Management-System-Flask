"""Report view/export integration tests."""

import pytest

from app.services import report_service

REPORT_SLUGS = list(report_service.REPORTS)


@pytest.mark.parametrize("slug", REPORT_SLUGS)
def test_report_view_renders(admin_client, slug):
    assert admin_client.get(f"/reports/{slug}").status_code == 200


@pytest.mark.parametrize("slug", REPORT_SLUGS)
def test_report_csv_export(admin_client, slug):
    resp = admin_client.get(f"/reports/{slug}/export.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert resp.headers["Content-Disposition"].startswith("attachment;")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_reports_index(admin_client):
    assert admin_client.get("/reports/").status_code == 200


def test_unknown_report_returns_404(admin_client):
    assert admin_client.get("/reports/does-not-exist").status_code == 404


def test_reports_require_admin(client):
    assert client.get("/reports/").status_code == 302


def test_student_register_csv_contains_data(admin_client, make_student):
    student = make_student()
    resp = admin_client.get("/reports/student-register/export.csv")
    assert b"Roll Number" in resp.data
    assert student.roll_number.encode() in resp.data


def test_occupancy_pdf(admin_client, room):
    resp = admin_client.get("/reports/occupancy.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:4] == b"%PDF"


def test_financial_summary_pdf(admin_client, room, make_student, fee_structures):
    from app.services import allocation_service, fee_service

    student = make_student()
    allocation_service.allocate_bed(student)
    fee_service.generate_fee(student, "2099-03")

    resp = admin_client.get("/reports/financial.pdf")
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"
