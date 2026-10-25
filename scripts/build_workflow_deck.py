"""Generate an animated, step-by-step workflow deck for the hostel app.

Produces ``Hostel_Workflow_Guide.pptx`` in the project root.  Each workflow is
broken into one slide per step; a progress rail across the top lights up one
node per slide (green = done, blue = current, grey = ahead) so that clicking
through the deck presents the workflow "pin to pin" (end to end).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "Hostel_Workflow_Guide.pptx"

# --- palette ---------------------------------------------------------------
INK = "0F172A"
INK2 = "334155"
MUTED = "64748B"
LINE = "E2E8F0"
ACCENT = "2563EB"
ACCENT2 = "1D4ED8"
ACCENT_SOFT = "93C5FD"
SOFT = "EFF4FF"
DONE = "16A34A"
WARN = "D97706"
VIOLET = "7C3AED"
CARD = "F8FAFC"
WHITE = "FFFFFF"
CHIP = "EEF2F7"
ARROW = "94A3B8"
FONT = "Segoe UI"

HOSTEL_NAME = "Sunrise Student Hostel"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

ROLE_COLORS = {"ADMIN": ACCENT, "STUDENT": VIOLET, "ADMIN + STUDENT": WARN}


# --- primitives ------------------------------------------------------------
def new_slide():
    slide = prs.slides.add_slide(BLANK)
    _add_fade(slide)
    return slide


def _add_fade(slide):
    sld = slide._element
    for existing in sld.findall(qn("p:transition")):
        sld.remove(existing)
    trans = sld.makeelement(qn("p:transition"), {"spd": "med"})
    trans.append(sld.makeelement(qn("p:fade"), {}))
    ref = sld.find(qn("p:clrMapOvr"))
    if ref is None:
        ref = sld.find(qn("p:cSld"))
    ref.addnext(trans)


def box(
    slide, x, y, w, h, fill=None, line=None, lw=1.0, radius=0.12, shape=MSO_SHAPE.ROUNDED_RECTANGLE
):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor.from_string(fill)
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = RGBColor.from_string(line)
        shp.line.width = Pt(lw)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        with contextlib.suppress(IndexError, ValueError):
            shp.adjustments[0] = radius
    shp.shadow.inherit = False
    return shp


def _fill(tf, lines):
    tf.clear()
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ln.get("align", PP_ALIGN.LEFT)
        p.level = ln.get("level", 0)
        if "space_after" in ln:
            p.space_after = Pt(ln["space_after"])
        if "space_before" in ln:
            p.space_before = Pt(ln["space_before"])
        runs = ln.get("runs") or [{"text": ln.get("text", "")}]
        for r in runs:
            run = p.add_run()
            run.text = r.get("text", "")
            f = run.font
            f.size = Pt(r.get("size", ln.get("size", 14)))
            f.bold = r.get("bold", ln.get("bold", False))
            f.italic = r.get("italic", ln.get("italic", False))
            f.name = FONT
            f.color.rgb = RGBColor.from_string(r.get("color", ln.get("color", INK2)))


def txt(slide, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0)
    _fill(tf, lines)
    return tb


def shape_text(shp, lines, anchor=MSO_ANCHOR.MIDDLE, m=0.06):
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(m)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    _fill(tf, lines)


def bullets(items, size=13, color=INK2, gap=7):
    return [
        {
            "runs": [
                {"text": "\u2022  ", "color": ACCENT, "size": size, "bold": True},
                {"text": t, "color": color, "size": size},
            ],
            "space_after": gap,
        }
        for t in items
    ]


# --- slide templates -------------------------------------------------------
def header(slide, title, subtitle=None):
    box(slide, 0.5, 0.55, 0.09, 0.52, fill=ACCENT, shape=MSO_SHAPE.RECTANGLE)
    txt(
        slide,
        0.76,
        0.5,
        11.9,
        0.7,
        [{"runs": [{"text": title, "size": 26, "bold": True, "color": INK}]}],
    )
    if subtitle:
        txt(
            slide,
            0.78,
            1.06,
            11.9,
            0.4,
            [{"runs": [{"text": subtitle, "size": 13, "color": MUTED}]}],
        )


def draw_rail(slide, nodes, current, caption):
    txt(
        slide,
        0.5,
        0.08,
        12.3,
        0.24,
        [{"runs": [{"text": caption.upper(), "size": 9, "bold": True, "color": ACCENT}]}],
    )
    n = len(nodes)
    left, right, gap = 0.5, 12.833, 0.14
    w = (right - left - gap * (n - 1)) / n
    y, h = 0.4, 0.48
    for i, name in enumerate(nodes):
        x = left + i * (w + gap)
        if i == current:
            fill, tcol, line, cy, ch = ACCENT, WHITE, ACCENT2, y - 0.06, h + 0.12
        elif i < current:
            fill, tcol, line, cy, ch = DONE, WHITE, None, y, h
        else:
            fill, tcol, line, cy, ch = CHIP, "94A3B8", None, y, h
        shp = box(slide, x, cy, w, ch, fill=fill, line=line, lw=1.5, radius=0.3)
        shape_text(
            shp,
            [
                {
                    "align": PP_ALIGN.CENTER,
                    "runs": [
                        {"text": f"{i + 1}  ", "size": 9.5, "bold": True, "color": tcol},
                        {"text": name, "size": 9.5, "bold": (i == current), "color": tcol},
                    ],
                }
            ],
        )


def info_card(slide, x, y, w, h, label, value, accent=ACCENT):
    box(slide, x, y, w, h, fill=WHITE, line=LINE, radius=0.09)
    box(slide, x, y, 0.1, h, fill=accent, shape=MSO_SHAPE.RECTANGLE)
    txt(
        slide,
        x + 0.3,
        y + 0.13,
        w - 0.5,
        h - 0.2,
        [
            {
                "runs": [{"text": label.upper(), "size": 9, "bold": True, "color": accent}],
                "space_after": 3,
            },
            {"runs": [{"text": value, "size": 12, "color": INK}]},
        ],
    )


def step_slide(caption, nodes, index, step):
    s = new_slide()
    draw_rail(s, nodes, index, caption)
    box(s, 0.5, 1.2, 7.0, 5.9, fill=CARD, line=LINE, radius=0.04)
    txt(
        s,
        0.85,
        1.5,
        6.35,
        1.1,
        [
            {
                "runs": [
                    {"text": f"STEP {index + 1}   ", "size": 12, "bold": True, "color": ACCENT},
                    {"text": step["title"], "size": 20, "bold": True, "color": INK},
                ],
                "space_after": 6,
            },
            {"runs": [{"text": step["route"], "size": 11.5, "italic": True, "color": MUTED}]},
        ],
    )
    txt(s, 0.85, 2.75, 6.35, 4.15, bullets(step["bullets"]), anchor=MSO_ANCHOR.TOP)

    rx, rw, ch, gap = 7.75, 5.083, 1.25, 0.2
    start = 1.2 + (5.9 - (4 * ch + 3 * gap)) / 2
    info_card(s, rx, start + 0 * (ch + gap), rw, ch, "Route", step["route"])
    info_card(s, rx, start + 1 * (ch + gap), rw, ch, "Data flow", step["data"])
    info_card(s, rx, start + 2 * (ch + gap), rw, ch, "Code", step["files"], accent=VIOLET)
    info_card(s, rx, start + 3 * (ch + gap), rw, ch, "Guardrails", step["guard"], accent=WARN)
    return s


def overview_slide(title, subtitle, nodes):
    s = new_slide()
    header(s, title, subtitle)
    cols = [0.75, 3.9, 7.05, 10.2]
    w, h = 2.4, 1.0
    row1, row2 = 2.15, 4.55
    pos = {}
    for k in range(4):
        pos[k] = (cols[k], row1)
    for j in range(4):
        pos[4 + j] = (cols[3 - j], row2)

    for i, name in enumerate(nodes):
        x, y = pos[i]
        b = box(s, x, y, w, h, fill=WHITE, line=ACCENT, lw=1.5, radius=0.1)
        shape_text(
            b,
            [
                {
                    "align": PP_ALIGN.CENTER,
                    "space_after": 2,
                    "runs": [{"text": f"STEP {i + 1}", "size": 9, "bold": True, "color": ACCENT}],
                },
                {
                    "align": PP_ALIGN.CENTER,
                    "runs": [
                        {"text": name.replace("\n", " "), "size": 13, "bold": True, "color": INK}
                    ],
                },
            ],
        )

    for k in range(3):
        box(
            s,
            cols[k] + w + 0.06,
            row1 + h / 2 - 0.16,
            0.63,
            0.32,
            fill=ARROW,
            shape=MSO_SHAPE.RIGHT_ARROW,
        )
    down_h = row2 - (row1 + h) - 0.16
    box(
        s,
        cols[3] + w / 2 - 0.16,
        row1 + h + 0.08,
        0.32,
        down_h,
        fill=ARROW,
        shape=MSO_SHAPE.DOWN_ARROW,
    )
    for k in range(3):
        box(
            s,
            cols[2 - k] + w + 0.06,
            row2 + h / 2 - 0.16,
            0.63,
            0.32,
            fill=ARROW,
            shape=MSO_SHAPE.LEFT_ARROW,
        )
    return s


# --- content ---------------------------------------------------------------
ADMIN_NODES = [
    "Sign in",
    "Dashboard",
    "Hostels & Rooms",
    "Students",
    "Allocations",
    "Fees",
    "Payments",
    "Reports & Audit",
]
STUDENT_NODES = [
    "Sign up",
    "Sign in",
    "Dashboard",
    "Profile",
    "Allocations",
    "Fees",
    "Payments",
    "Receipts",
]

ADMIN_STEPS = [
    {
        "title": "Admin signs in",
        "route": "/auth/login \u2192 /admin/",
        "bullets": [
            "Admin submits email + password; the hash is verified.",
            "A successful login stamps last_login_at and opens a Flask-Login session.",
            "The role decides the landing page: admins \u2192 dashboard, students \u2192 portal.",
            "Failed logins show a generic error and are rate-limited (10/min).",
        ],
        "files": "app/auth/routes.py \u00b7 app/utils/decorators.py",
        "data": "credentials \u2192 authenticated session",
        "guard": "rate-limited \u00b7 no account enumeration \u00b7 role-based redirect",
    },
    {
        "title": "Operational dashboard",
        "route": "/admin/  (admin.dashboard)",
        "bullets": [
            "Aggregates live figures straight from the database \u2014 nothing cached.",
            "Students (total / active / inactive), rooms, capacity, occupied & free beds.",
            "Monthly collection, total outstanding and overdue record count.",
            "The 6 most recent payments and allocations.",
            "Charts: occupancy by room type, by hostel, and a 6-month collection trend.",
        ],
        "files": "app/admin/routes.py \u00b7 app/services/dashboard_service.py",
        "data": "SQL aggregates \u2192 KPI cards + charts",
        "guard": "admin_required",
    },
    {
        "title": "Set up hostels and rooms",
        "route": "/hostels \u00b7 /rooms",
        "bullets": [
            "Create a hostel (name, address) first \u2014 every room belongs to a hostel.",
            "Add rooms: type (single/double/dormitory), capacity, base fee, status.",
            "Room numbers are unique per hostel.",
            "Capacity can never drop below current occupancy.",
            "Rooms with allocation history cannot be deleted \u2014 mark them unavailable.",
        ],
        "files": "app/rooms/routes.py \u00b7 app/rooms/forms.py",
        "data": "form input \u2192 Hostel / Room rows",
        "guard": "capacity \u2265 occupancy \u00b7 unique number \u00b7 audit logged",
    },
    {
        "title": "Onboard and manage students",
        "route": "/students",
        "bullets": [
            "Create a student record and optionally their portal login in one step.",
            "Filter the roster by course, year, status, allocation and fee state.",
            "Open a student to see profile + allocations + fees + payments together.",
            "Deactivating or archiving automatically releases their active room.",
        ],
        "files": "app/students/routes.py",
        "data": "profile \u2192 Student (+ linked User)",
        "guard": "unique email & roll no \u00b7 deactivation frees the bed",
    },
    {
        "title": "Assign beds",
        "route": "/allocations  (auto \u00b7 manual \u00b7 transfer \u00b7 release)",
        "bullets": [
            "Auto-allocate picks the lowest free bed in the first eligible room.",
            "Manual assign and transfer release then re-allocate atomically.",
            "Release frees the bed but keeps the row as immutable history.",
            "Concurrency-safe: FOR UPDATE SKIP LOCKED + partial unique indexes + trigger.",
        ],
        "files": "app/allocations/routes.py \u00b7 app/services/allocation_service.py",
        "data": "student + room \u2192 active RoomAllocation",
        "guard": "no double-booking \u00b7 one active bed per student \u00b7 retries",
    },
    {
        "title": "Generate and adjust monthly bills",
        "route": "/fees  (+ /fees/structures)",
        "bullets": [
            "Fee structures per room type set default monthly / mess / laundry / maintenance.",
            "Generate bills for a period (YYYY-MM); duplicates are skipped.",
            "Bill = accommodation + extras \u2212 discount, plus a late fee after grace.",
            "Status is derived: paid / partial / overdue / pending.",
        ],
        "files": "app/fees/routes.py \u00b7 app/services/fee_service.py",
        "data": "rooms + structures + period \u2192 StudentFee rows",
        "guard": "Decimal money \u00b7 idempotent generation \u00b7 late fee after grace",
    },
    {
        "title": "Record payments and issue receipts",
        "route": "/payments",
        "bullets": [
            "Record a payment against a fee; an idempotency key prevents duplicates.",
            "The fee row is locked (FOR UPDATE) and overpayment is rejected.",
            "Payments are immutable \u2014 corrections create a linked reversal record.",
            "A PDF receipt can be generated for any payment.",
        ],
        "files": "app/payments/routes.py \u00b7 app/services/payment_service.py",
        "data": "payment \u2192 Payment row \u2192 balance / status update",
        "guard": "idempotent \u00b7 no overpay \u00b7 immutable + reversal \u00b7 receipt PDF",
    },
    {
        "title": "Reports, audit and settings",
        "route": "/reports \u00b7 /admin/audit \u00b7 /admin/settings",
        "bullets": [
            "Slug-based reports, each viewable and exportable to CSV.",
            "Occupancy and financial summary PDFs.",
            "Audit log records who changed what \u2014 filter by action, entity, date.",
            "Settings hold hostel identity, currency symbol and late-fee policy.",
        ],
        "files": "reports/routes.py \u00b7 admin/routes.py \u00b7 services/audit_service.py",
        "data": "DB \u2192 CSV / PDF \u00b7 every write \u2192 audit entry",
        "guard": "admin_required \u00b7 immutable audit trail",
    },
]

STUDENT_STEPS = [
    {
        "title": "Create a portal account",
        "route": "/auth/signup",
        "bullets": [
            "Signup creates the User (role = student) and the Student profile together.",
            "Email and roll number must be unique.",
            "New accounts link straight to the student portal.",
        ],
        "files": "app/auth/routes.py",
        "data": "signup form \u2192 User + Student",
        "guard": "signup rate-limited \u00b7 unique email & roll no",
    },
    {
        "title": "Student signs in",
        "route": "/auth/login \u2192 /portal",
        "bullets": [
            "Same login endpoint as admins \u2014 the role decides where you land.",
            "Students are always routed to the portal dashboard.",
        ],
        "files": "app/auth/routes.py",
        "data": "credentials \u2192 session",
        "guard": "rate-limited \u00b7 role redirect \u00b7 generic errors",
    },
    {
        "title": "Personal dashboard",
        "route": "/portal",
        "bullets": [
            "Shows the current room allocation and recent payments.",
            "Surfaces the upcoming due bill and totals: billed, paid, outstanding.",
            "Everything is scoped to the logged-in student.",
        ],
        "files": "app/students/portal.py",
        "data": "own fees / payments / allocation \u2192 summary",
        "guard": "student_required \u00b7 self-scoped",
    },
    {
        "title": "Profile self-service",
        "route": "/portal/profile \u00b7 /portal/profile/edit",
        "bullets": [
            "View the profile; edit only phone, address and emergency contact.",
            "Identity fields (name, roll number, course, year) stay admin-controlled.",
        ],
        "files": "app/students/portal.py",
        "data": "limited form \u2192 Student",
        "guard": "editable fields restricted",
    },
    {
        "title": "My room",
        "route": "/portal/allocations",
        "bullets": [
            "Current bed and the full allocation history.",
            "Read-only \u2014 allocation is an admin action.",
        ],
        "files": "app/students/portal.py",
        "data": "own allocations \u2192 list",
        "guard": "self-scoped",
    },
    {
        "title": "My bills",
        "route": "/portal/fees \u00b7 /portal/fees/<id>",
        "bullets": [
            "Monthly bills with amount, paid, balance and status.",
            "Per-bill detail shows the breakdown and due date.",
            "Opening another student's bill returns 404.",
        ],
        "files": "app/students/portal.py",
        "data": "own StudentFee rows \u2192 list / detail",
        "guard": "IDOR-safe (404 on others)",
    },
    {
        "title": "My payments",
        "route": "/portal/payments",
        "bullets": [
            "History of payments recorded against the account.",
            "Read-only \u2014 recording is an admin action.",
        ],
        "files": "app/students/portal.py",
        "data": "own Payment rows \u2192 list",
        "guard": "self-scoped",
    },
    {
        "title": "Download receipts",
        "route": "/portal/receipts/<id>",
        "bullets": [
            "Download a PDF receipt for any of your own payments.",
            "Requesting a receipt that is not yours returns 404.",
        ],
        "files": "app/students/portal.py",
        "data": "payment id \u2192 own PDF",
        "guard": "IDOR-safe (404 on others)",
    },
]

LIFECYCLE = [
    ("Set up hostels\n& rooms", "ADMIN"),
    ("Enroll\nstudents", "ADMIN + STUDENT"),
    ("Allocate\nbeds", "ADMIN"),
    ("Generate\nmonthly fees", "ADMIN"),
    ("Record\npayments", "ADMIN"),
    ("View bills &\nreceipts", "STUDENT"),
    ("Reports, audit &\ndeactivate", "ADMIN"),
]


# --- build -----------------------------------------------------------------
def title_slide():
    s = new_slide()
    box(s, 0, 0, 13.333, 7.5, fill=INK, shape=MSO_SHAPE.RECTANGLE)
    box(s, 0.9, 2.0, 0.14, 2.4, fill=ACCENT, shape=MSO_SHAPE.RECTANGLE)
    txt(
        s,
        1.25,
        1.95,
        11.2,
        1.0,
        [
            {
                "runs": [
                    {"text": "Hostel Management System", "size": 40, "bold": True, "color": WHITE}
                ]
            }
        ],
    )
    txt(
        s,
        1.28,
        3.0,
        11.2,
        0.6,
        [
            {
                "runs": [
                    {
                        "text": "Admin & Student Portal \u2014 end-to-end workflow",
                        "size": 19,
                        "color": ACCENT_SOFT,
                    }
                ]
            }
        ],
    )
    txt(
        s,
        1.28,
        3.7,
        11.2,
        0.5,
        [
            {
                "runs": [
                    {
                        "text": "A step-by-step, pin-to-pin walkthrough of both portals.",
                        "size": 13,
                        "color": MUTED,
                    }
                ]
            }
        ],
    )
    box(s, 0.9, 5.9, 3.2, 0.02, fill=INK2, shape=MSO_SHAPE.RECTANGLE)
    txt(
        s,
        0.9,
        6.05,
        11.0,
        0.4,
        [
            {
                "runs": [
                    {
                        "text": f"{HOSTEL_NAME}  \u00b7  Flask + PostgreSQL",
                        "size": 12,
                        "color": MUTED,
                    }
                ]
            }
        ],
    )
    return s


def architecture_slide():
    s = new_slide()
    header(
        s,
        "Two portals, one system",
        "One Flask app and database; the landing page is decided by the account role.",
    )
    cols = [
        (
            0.6,
            3.75,
            "Admin portal",
            ACCENT,
            "/admin",
            [
                "Hostels & rooms",
                "Students",
                "Allocations",
                "Fees",
                "Payments",
                "Reports & audit",
                "Settings",
            ],
        ),
        (
            4.75,
            3.83,
            "Shared core",
            INK,
            "app/",
            [
                "Auth & role checks",
                "Flask-Login sessions",
                "SQLAlchemy models + services",
                "PostgreSQL integrity rules",
                "Audit logging",
            ],
        ),
        (
            8.98,
            3.75,
            "Student portal",
            VIOLET,
            "/portal",
            ["Dashboard", "Profile", "My room", "My bills", "My payments", "Receipts"],
        ),
    ]
    for x, w, heading, color, tag, items in cols:
        box(s, x, 1.7, w, 4.75, fill=WHITE, line=LINE, radius=0.06)
        box(s, x, 1.7, w, 0.62, fill=color, radius=0.06)
        txt(
            s,
            x + 0.25,
            1.8,
            w - 0.5,
            0.45,
            [{"runs": [{"text": heading, "size": 15, "bold": True, "color": WHITE}]}],
        )
        txt(
            s,
            x + 0.25,
            2.5,
            w - 0.5,
            0.3,
            [{"runs": [{"text": tag, "size": 10.5, "italic": True, "color": MUTED}]}],
        )
        txt(s, x + 0.25, 2.95, w - 0.5, 3.3, bullets(items, size=12.5, gap=9))
    box(s, 0.6, 6.7, 12.13, 0.55, fill=SOFT, line=LINE, radius=0.12)
    txt(
        s,
        0.85,
        6.8,
        11.7,
        0.4,
        [
            {
                "runs": [
                    {"text": "Role routing:  ", "size": 12, "bold": True, "color": ACCENT},
                    {
                        "text": "admin \u2192 /admin  \u00b7  student \u2192 /portal  "
                        "(decided at login)",
                        "size": 12,
                        "color": INK,
                    },
                ]
            }
        ],
    )
    return s


def lifecycle_slide():
    s = new_slide()
    header(
        s,
        "How the two portals connect",
        "The data lifecycle: the admin creates and bills; the student views and pays down.",
    )
    left, right, gap = 0.5, 12.833, 0.25
    n = len(LIFECYCLE)
    w = (right - left - gap * (n - 1)) / n
    y, h = 2.9, 1.9
    for i, (label, role) in enumerate(LIFECYCLE):
        x = left + i * (w + gap)
        color = ROLE_COLORS[role]
        box(s, x + w / 2 - 0.55, 2.35, 1.1, 0.3, fill=color, radius=0.4)
        txt(
            s,
            x + w / 2 - 0.55,
            2.39,
            1.1,
            0.25,
            [
                {
                    "align": PP_ALIGN.CENTER,
                    "runs": [{"text": role, "size": 8, "bold": True, "color": WHITE}],
                }
            ],
        )
        b = box(s, x, y, w, h, fill=WHITE, line=color, lw=1.75, radius=0.1)
        shape_text(
            b,
            [
                {
                    "align": PP_ALIGN.CENTER,
                    "space_after": 4,
                    "runs": [{"text": f"{i + 1}", "size": 20, "bold": True, "color": color}],
                },
                {
                    "align": PP_ALIGN.CENTER,
                    "runs": [
                        {"text": label.replace("\n", " "), "size": 11, "bold": True, "color": INK}
                    ],
                },
            ],
        )
        if i < n - 1:
            box(
                s,
                x + w + 0.02,
                y + h / 2 - 0.12,
                gap - 0.04,
                0.24,
                fill=ARROW,
                shape=MSO_SHAPE.RIGHT_ARROW,
            )
    box(s, 0.5, 5.35, 12.333, 0.7, fill=SOFT, line=LINE, radius=0.14)
    txt(
        s,
        0.8,
        5.5,
        11.8,
        0.45,
        [
            {
                "runs": [
                    {"text": "\u21bb  ", "size": 15, "bold": True, "color": ACCENT},
                    {
                        "text": "The cycle repeats every billing month: bill \u2192 pay \u2192 "
                        "reconcile \u2192 report \u2192 re-allocate as students move.",
                        "size": 12.5,
                        "color": INK,
                    },
                ]
            }
        ],
    )
    txt(
        s,
        0.8,
        6.25,
        11.8,
        0.4,
        [
            {
                "runs": [
                    {
                        "text": "Deactivating a student closes the loop by automatically "
                        "releasing their bed.",
                        "size": 11.5,
                        "italic": True,
                        "color": MUTED,
                    }
                ]
            }
        ],
    )
    return s


def closing_slide():
    s = new_slide()
    header(s, "Key guarantees & how to present")
    left = [
        "Role-checked on every route (admin_required / student_required).",
        "DB-level integrity: partial unique indexes + capacity triggers.",
        "Payments are immutable; corrections are linked reversal records.",
        "Student data is self-scoped \u2014 other records return 404.",
        "Deterministic Decimal billing (no floating-point drift).",
        "Full audit trail on every state change.",
    ]
    right = [
        "Present it one step at a time: the progress rail turns each node",
        "green \u2192 blue \u2192 grey as you advance, giving a pin-to-pin build.",
        "Add a Morph or Fade transition in PowerPoint for extra motion",
        "(fade is already applied to every slide).",
        "Use the two overview slides as the map, the step slides as the detail.",
    ]
    box(s, 0.6, 1.7, 6.0, 5.0, fill=WHITE, line=LINE, radius=0.05)
    txt(
        s,
        0.9,
        1.95,
        5.5,
        0.4,
        [{"runs": [{"text": "GUARANTEES", "size": 10, "bold": True, "color": ACCENT}]}],
    )
    txt(s, 0.9, 2.45, 5.5, 4.1, bullets(left, size=13, gap=12))
    box(s, 6.95, 1.7, 5.78, 5.0, fill=SOFT, line=LINE, radius=0.05)
    txt(
        s,
        7.25,
        1.95,
        5.2,
        0.4,
        [{"runs": [{"text": "PRESENTING", "size": 10, "bold": True, "color": VIOLET}]}],
    )
    txt(s, 7.25, 2.45, 5.2, 4.1, bullets(right, size=13, gap=12))
    return s


def build():
    title_slide()
    architecture_slide()
    overview_slide(
        "Admin portal \u2014 workflow map",
        "Eight steps from sign-in to reporting. Details follow on the next slides.",
        ADMIN_NODES,
    )
    for i, step in enumerate(ADMIN_STEPS):
        step_slide("Admin portal \u2014 step-by-step", ADMIN_NODES, i, step)
    overview_slide(
        "Student portal \u2014 workflow map",
        "Eight steps from sign-up to receipts. Details follow on the next slides.",
        STUDENT_NODES,
    )
    for i, step in enumerate(STUDENT_STEPS):
        step_slide("Student portal \u2014 step-by-step", STUDENT_NODES, i, step)
    lifecycle_slide()
    closing_slide()
    prs.save(OUT)
    print(f"Wrote {OUT} with {len(prs.slides._sldIdLst)} slides")


if __name__ == "__main__":
    build()
