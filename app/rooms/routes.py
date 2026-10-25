"""Hostel and room management routes."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.constants import ROOM_STATUSES, ROOM_TYPES
from app.extensions import db
from app.models import Hostel, Room, RoomAllocation
from app.services import audit_service
from app.utils.decorators import admin_required, flash_form_errors
from app.utils.pagination import page_args, query_string_without_page

from . import hostels_bp, rooms_bp
from .forms import HostelForm, RoomForm


# ---------------------------------------------------------------------------
# Hostels
# ---------------------------------------------------------------------------
@hostels_bp.route("/")
@admin_required
def list_hostels():
    hostels = db.session.execute(select(Hostel).order_by(Hostel.name)).scalars().all()
    return render_template("rooms/hostels.html", hostels=hostels)


@hostels_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create_hostel():
    form = HostelForm()
    if form.validate_on_submit():
        hostel = Hostel(
            name=form.name.data.strip(),
            address=form.address.data,
            description=form.description.data,
        )
        db.session.add(hostel)
        db.session.flush()
        audit_service.log_action("hostel.create", "hostel", hostel.id, {"name": hostel.name})
        db.session.commit()
        flash("Hostel created.", "success")
        return redirect(url_for("hostels.list_hostels"))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("rooms/hostel_form.html", form=form, hostel=None)


@hostels_bp.route("/<int:hostel_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_hostel(hostel_id):
    hostel = db.session.get(Hostel, hostel_id) or abort(404)
    form = HostelForm(obj=hostel, hostel=hostel)
    if form.validate_on_submit():
        hostel.name = form.name.data.strip()
        hostel.address = form.address.data
        hostel.description = form.description.data
        audit_service.log_action("hostel.update", "hostel", hostel.id)
        db.session.commit()
        flash("Hostel updated.", "success")
        return redirect(url_for("hostels.list_hostels"))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("rooms/hostel_form.html", form=form, hostel=hostel)


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------
@rooms_bp.route("/")
@admin_required
def list_rooms():
    page, per_page = page_args()
    stmt = select(Room).join(Hostel, Hostel.id == Room.hostel_id)

    search = (request.args.get("q") or "").strip()
    if search:
        stmt = stmt.where(Room.room_number.ilike(f"%{search}%"))
    if request.args.get("hostel_id"):
        stmt = stmt.where(Room.hostel_id == int(request.args["hostel_id"]))
    if request.args.get("room_type") in ROOM_TYPES:
        stmt = stmt.where(Room.room_type == request.args["room_type"])
    if request.args.get("status") in ROOM_STATUSES:
        stmt = stmt.where(Room.status == request.args["status"])

    stmt = stmt.order_by(Hostel.name, Room.room_number)
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    hostels = db.session.execute(select(Hostel).order_by(Hostel.name)).scalars().all()
    return render_template(
        "rooms/list.html",
        pagination=pagination,
        rooms=pagination.items,
        hostels=hostels,
        room_types=ROOM_TYPES,
        filters=request.args,
        query_string=query_string_without_page(),
    )


@rooms_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create_room():
    if db.session.execute(select(Hostel)).first() is None:
        flash("Create a hostel before adding rooms.", "warning")
        return redirect(url_for("hostels.create_hostel"))
    form = RoomForm()
    if form.validate_on_submit():
        room = Room(
            hostel_id=form.hostel_id.data,
            room_number=form.room_number.data.strip(),
            floor=form.floor.data,
            room_type=form.room_type.data,
            capacity=form.capacity.data,
            base_fee=form.base_fee.data,
            status=form.status.data,
            amenities=form.amenities.data,
        )
        db.session.add(room)
        try:
            db.session.flush()
            audit_service.log_action("room.create", "room", room.id, {"number": room.room_number})
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That room number already exists in the selected hostel.", "danger")
            return render_template("rooms/form.html", form=form, room=None)
        flash("Room created.", "success")
        return redirect(url_for("rooms.view_room", room_id=room.id))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("rooms/form.html", form=form, room=None)


@rooms_bp.route("/<int:room_id>")
@admin_required
def view_room(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    occupants = list(room.active_allocations)
    history = (
        db.session.execute(
            select(RoomAllocation)
            .where(RoomAllocation.room_id == room.id)
            .order_by(RoomAllocation.allocated_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template("rooms/detail.html", room=room, occupants=occupants, history=history)


@rooms_bp.route("/<int:room_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_room(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    form = RoomForm(obj=room, room=room)
    if form.validate_on_submit():
        old_capacity = room.capacity
        room.hostel_id = form.hostel_id.data
        room.room_number = form.room_number.data.strip()
        room.floor = form.floor.data
        room.room_type = form.room_type.data
        room.capacity = form.capacity.data
        room.base_fee = form.base_fee.data
        room.status = form.status.data
        room.amenities = form.amenities.data
        try:
            audit_service.log_action(
                "room.update",
                "room",
                room.id,
                {"capacity": [old_capacity, room.capacity]},
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That room number already exists in the selected hostel.", "danger")
            return render_template("rooms/form.html", form=form, room=room)
        flash("Room updated.", "success")
        return redirect(url_for("rooms.view_room", room_id=room.id))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("rooms/form.html", form=form, room=room)


@rooms_bp.post("/<int:room_id>/status")
@admin_required
def change_room_status(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    new_status = request.form.get("status")
    if new_status not in ROOM_STATUSES:
        flash("Invalid room status.", "danger")
    else:
        old = room.status
        room.status = new_status
        audit_service.log_action(
            "room.status_change", "room", room.id, {"from": old, "to": new_status}
        )
        db.session.commit()
        flash("Room status updated.", "success")
    return redirect(url_for("rooms.view_room", room_id=room.id))


@rooms_bp.post("/<int:room_id>/delete")
@admin_required
def delete_room(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    allocations = db.session.execute(
        select(RoomAllocation).where(RoomAllocation.room_id == room.id)
    ).first()
    if allocations is not None:
        flash(
            "This room has allocation history and cannot be deleted. Mark it unavailable instead.",
            "danger",
        )
        return redirect(url_for("rooms.view_room", room_id=room.id))
    number = room.room_number
    db.session.delete(room)
    audit_service.log_action("room.delete", "room", room_id, {"number": number})
    db.session.commit()
    flash("Room deleted.", "success")
    return redirect(url_for("rooms.list_rooms"))
