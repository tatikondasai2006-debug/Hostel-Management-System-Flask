"""Integration tests for the sidebar navigation and hostel/room information architecture.

These cover the branding/navigation changes: section structure, the
Hostels -> Rooms nesting, single active-state, contextual Operations tabs and
the shared logo reference.
"""

from __future__ import annotations

import re

LOGO = b"img/hostelms-logo.png"


def _sidebar_nav(body: bytes) -> bytes:
    match = re.search(rb'<nav class="hms-nav">.*?</nav>', body, re.DOTALL)
    assert match is not None
    return match.group(0)


def test_sidebar_has_expected_sections_and_labels(admin_client):
    resp = admin_client.get("/admin/")
    assert resp.status_code == 200
    body = resp.data
    assert b"hms-sidebar" in body
    for section in (b"Overview", b"Operations", b"Finance", b"System"):
        assert section in body, section
    for label in (
        b"Dashboard",
        b"Students",
        b"Hostels",
        b"Rooms",
        b"Allocations",
        b"Fees",
        b"Payments",
        b"Reports",
        b"Settings",
        b"Audit Log",
    ):
        assert label in body, label


def test_rooms_is_nested_under_hostels(admin_client):
    body = admin_client.get("/admin/").data
    assert b"nav-sub" in body
    # Rooms link is rendered with the nested sub-item class.
    assert b'href="/rooms/"' in body


def test_sidebar_references_brand_logo(admin_client):
    assert LOGO in admin_client.get("/admin/").data
    assert LOGO in admin_client.get("/hostels/").data


def test_single_active_nav_item_per_page(admin_client):
    # Exactly one sidebar link carries aria-current="page" on each page,
    # even when a contextual Operations tab is also active.
    for path in ("/admin/", "/hostels/", "/rooms/", "/admin/settings", "/admin/audit"):
        sidebar = _sidebar_nav(admin_client.get(path).data)
        assert sidebar.count(b'aria-current="page"') == 1, path


def test_hostels_page_has_ops_tabs(admin_client):
    body = admin_client.get("/hostels/").data
    assert b"hms-tabs" in body
    for label in (b"Students", b"Hostels", b"Rooms", b"Allocations"):
        assert label in body


def test_hostels_page_links_to_its_rooms(admin_client, hostel, make_room):
    make_room(hostel, number="B-1")
    body = admin_client.get("/hostels/").data
    assert f"/rooms/?hostel_id={hostel.id}".encode() in body


def test_rooms_page_filters_render(admin_client, hostel, make_room):
    make_room(hostel, number="B-101")
    resp = admin_client.get("/rooms/")
    assert resp.status_code == 200
    assert b"hms-tabs" in resp.data
    assert b"B-101" in resp.data
