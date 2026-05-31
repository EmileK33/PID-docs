"""S2-C — Symbols & Corrections endpoints: independent acceptance tests.

Run with:  pytest tests/sessions/test_s2c.py -v

Fully self-contained (in-memory SQLite via ``conftest.py``) so the bare-pytest
``session-tests`` gate — which boots no Docker services — runs every assertion
for real rather than skipping. The AC -> test mapping mirrors §S2-C's
"AC -> assertion mapping" table verbatim.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

# ``app.*`` imports are safe at module top: tests/sessions has no "no-app-import"
# smoke guard (that constraint is specific to tests/integration), and conftest
# has already seeded the env + sys.path.
from app.db.models.detected_symbol import DetectedSymbol
from app.db.models.drawing import Drawing
from app.db.models.user_correction import UserCorrection

EMIT_PATH = "app.services.correction_service.emit_correction_action"


def _bbox():
    return {"x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0}


# ===========================================================================
# US-011 — GET /drawings/{id}/symbols
# ===========================================================================
def test_list_symbols_returns_200_with_symbol_records(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    make_symbol(drawing_id=d.id, confidence=0.83)
    login(current_user_owner)

    resp = client.get(f"/drawings/{d.id}/symbols")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {
        "symbols",
        "corrections_by_symbol_id",
        "total",
        "limit",
        "offset",
    }
    assert len(body["symbols"]) == 1
    sym = body["symbols"][0]
    assert 0.0 <= sym["confidence"] <= 1.0
    assert sym["bbox"].keys() >= {"x", "y", "w", "h"}


def test_list_symbols_corrections_by_symbol_id_populated(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol, db
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    db.add(
        UserCorrection(
            detected_symbol_id=sym.id,
            user_id=owner_id,
            correction_type="reclassify",
            new_class_id="valve_ball",
            training_consent=False,
        )
    )
    db.commit()
    login(current_user_owner)

    body = client.get(f"/drawings/{d.id}/symbols").json()
    cbs = body["corrections_by_symbol_id"]
    assert str(sym.id) in cbs
    assert len(cbs[str(sym.id)]) == 1
    assert cbs[str(sym.id)][0]["correction_type"] == "reclassify"
    assert cbs[str(sym.id)][0]["new_class_id"] == "valve_ball"


def test_list_symbols_limit_default_200_cap_500(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    make_symbol(drawing_id=d.id)
    login(current_user_owner)

    default_body = client.get(f"/drawings/{d.id}/symbols").json()
    assert default_body["limit"] == 200

    assert client.get(f"/drawings/{d.id}/symbols?limit=500").status_code == 200
    assert client.get(f"/drawings/{d.id}/symbols?limit=501").status_code == 422


def test_list_symbols_page_number_filter(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    make_symbol(drawing_id=d.id, page_number=1)
    make_symbol(drawing_id=d.id, page_number=2)
    login(current_user_owner)

    body = client.get(f"/drawings/{d.id}/symbols?page_number=2").json()
    assert body["total"] == 1
    assert all(s["page_number"] == 2 for s in body["symbols"])


def test_list_symbols_entity_class_filter(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    make_symbol(drawing_id=d.id, entity_class_id="valve_gate")
    make_symbol(drawing_id=d.id, entity_class_id="pipe")
    login(current_user_owner)

    body = client.get(f"/drawings/{d.id}/symbols?entity_class_id=pipe").json()
    assert body["total"] == 1
    assert all(s["entity_class_id"] == "pipe" for s in body["symbols"])


def test_list_symbols_rejected_filter(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    make_symbol(drawing_id=d.id, rejected=False)
    make_symbol(drawing_id=d.id, rejected=True)
    login(current_user_owner)

    rejected = client.get(f"/drawings/{d.id}/symbols?rejected=true").json()
    assert rejected["total"] == 1
    assert all(s["rejected"] is True for s in rejected["symbols"])

    not_rejected = client.get(f"/drawings/{d.id}/symbols?rejected=false").json()
    assert not_rejected["total"] == 1
    assert all(s["rejected"] is False for s in not_rejected["symbols"])


def test_list_symbols_total_reflects_filter(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    for _ in range(3):
        make_symbol(drawing_id=d.id, entity_class_id="valve_gate")
    make_symbol(drawing_id=d.id, entity_class_id="pipe")
    login(current_user_owner)

    all_body = client.get(f"/drawings/{d.id}/symbols").json()
    assert all_body["total"] == 4
    filtered = client.get(
        f"/drawings/{d.id}/symbols?entity_class_id=valve_gate"
    ).json()
    assert filtered["total"] == 3


def test_list_symbols_unauthenticated_returns_401(
    client, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    make_symbol(drawing_id=d.id)
    # No login() -> the real get_current_user runs and rejects the missing token.
    resp = client.get(f"/drawings/{d.id}/symbols")
    assert resp.status_code == 401


def test_list_symbols_wrong_owner_returns_403(
    client, login, current_user_other, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    make_symbol(drawing_id=d.id)
    login(current_user_other)  # authenticated, but not the owner
    resp = client.get(f"/drawings/{d.id}/symbols")
    assert resp.status_code == 403


def test_list_symbols_drawing_not_found_returns_404(
    client, login, current_user_owner
):
    login(current_user_owner)
    resp = client.get(f"/drawings/{uuid.uuid4()}/symbols")
    assert resp.status_code == 404


# ===========================================================================
# US-012 — Under_Review transition on first correction
# ===========================================================================
def test_first_correction_transitions_drawing_to_under_review(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    d = make_drawing(owner_user_id=owner_id, state="Complete")
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    resp = client.patch(
        f"/symbols/{sym.id}", json={"correction_type": "reject"}
    )
    assert resp.status_code == 200
    with session_factory() as s:
        assert s.get(Drawing, d.id).processing_state == "Under_Review"


def test_correction_on_under_review_drawing_succeeds(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    d = make_drawing(owner_user_id=owner_id, state="Under_Review")
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    resp = client.patch(
        f"/symbols/{sym.id}", json={"correction_type": "reject"}
    )
    assert resp.status_code == 200
    with session_factory() as s:
        assert s.get(Drawing, d.id).processing_state == "Under_Review"


def test_get_symbols_does_not_trigger_under_review(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    d = make_drawing(owner_user_id=owner_id, state="Complete")
    make_symbol(drawing_id=d.id)
    login(current_user_owner)

    client.get(f"/drawings/{d.id}/symbols")
    with session_factory() as s:
        assert s.get(Drawing, d.id).processing_state == "Complete"


def test_concurrent_corrections_no_constraint_violation(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    # The Under_Review transition is a conditional UPDATE (... WHERE state =
    # 'Complete'); a second correction finds it already transitioned and must
    # succeed without error or duplicate-transition fallout.
    d = make_drawing(owner_user_id=owner_id, state="Complete")
    s1 = make_symbol(drawing_id=d.id)
    s2 = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    r1 = client.patch(f"/symbols/{s1.id}", json={"correction_type": "reject"})
    r2 = client.patch(f"/symbols/{s2.id}", json={"correction_type": "reject"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    with session_factory() as s:
        assert s.get(Drawing, d.id).processing_state == "Under_Review"


# ===========================================================================
# US-013 — PATCH /symbols/{id}: reclassify / reject / restore
# ===========================================================================
def test_patch_reclassify_creates_correction_and_updates_class(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory, count_corrections,
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id, entity_class_id="valve_gate")
    login(current_user_owner)

    resp = client.patch(
        f"/symbols/{sym.id}",
        json={"correction_type": "reclassify", "new_class_id": "valve_ball"},
    )
    assert resp.status_code == 200
    assert resp.json()["entity_class_id"] == "valve_ball"
    assert count_corrections(sym.id) == 1
    with session_factory() as s:
        assert s.get(DetectedSymbol, sym.id).entity_class_id == "valve_ball"


def test_patch_reject_sets_rejected_true(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id, rejected=False)
    login(current_user_owner)

    resp = client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})
    assert resp.status_code == 200
    assert resp.json()["rejected"] is True
    with session_factory() as s:
        assert s.get(DetectedSymbol, sym.id).rejected is True


def test_patch_restore_sets_rejected_false(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id, rejected=True)
    login(current_user_owner)

    resp = client.patch(f"/symbols/{sym.id}", json={"correction_type": "restore"})
    assert resp.status_code == 200
    assert resp.json()["rejected"] is False
    with session_factory() as s:
        assert s.get(DetectedSymbol, sym.id).rejected is False


def test_patch_reclassify_without_new_class_id_returns_422(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    resp = client.patch(
        f"/symbols/{sym.id}", json={"correction_type": "reclassify"}
    )
    assert resp.status_code == 422


def test_patch_reclassify_invalid_class_id_returns_422(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    resp = client.patch(
        f"/symbols/{sym.id}",
        json={"correction_type": "reclassify", "new_class_id": "not_a_class"},
    )
    assert resp.status_code == 422


def test_patch_manual_add_correction_type_returns_422(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    resp = client.patch(
        f"/symbols/{sym.id}", json={"correction_type": "manual_add"}
    )
    assert resp.status_code == 422


def test_patch_symbol_success_returns_200_with_symbol_record(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    resp = client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(sym.id)
    assert body["drawing_id"] == str(d.id)
    assert set(body) >= {"id", "drawing_id", "entity_class_id", "bbox", "source"}


def test_patch_symbol_not_found_returns_404(client, login, current_user_owner):
    login(current_user_owner)
    resp = client.patch(
        f"/symbols/{uuid.uuid4()}", json={"correction_type": "reject"}
    )
    assert resp.status_code == 404


def test_patch_symbol_wrong_owner_returns_403(
    client, login, current_user_other, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_other)
    resp = client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})
    assert resp.status_code == 403


def test_patch_symbol_unauthenticated_returns_401(
    client, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    resp = client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})
    assert resp.status_code == 401


# ===========================================================================
# US-014 — POST /drawings/{id}/symbols: manual annotation
# ===========================================================================
def _manual_body(**overrides):
    body = {
        "entity_class_id": "valve_ball",
        "subtype": "ball",
        "tag_label": "V-200",
        "bbox": _bbox(),
        "page_number": 1,
    }
    body.update(overrides)
    return body


def test_post_symbol_creates_manual_with_source_and_confidence(
    client, login, current_user_owner, owner_id, make_drawing, session_factory
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)

    resp = client.post(f"/drawings/{d.id}/symbols", json=_manual_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "manual"
    assert body["confidence"] == 1.0
    assert body["entity_class_id"] == "valve_ball"
    with session_factory() as s:
        row = s.get(DetectedSymbol, uuid.UUID(body["id"]))
        assert row.source == "manual"
        assert row.confidence == 1.0


def test_post_symbol_creates_manual_add_correction_record(
    client, login, current_user_owner, owner_id, make_drawing, session_factory
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)

    body = client.post(f"/drawings/{d.id}/symbols", json=_manual_body()).json()
    with session_factory() as s:
        from sqlalchemy import select

        rows = (
            s.execute(
                select(UserCorrection).where(
                    UserCorrection.detected_symbol_id == uuid.UUID(body["id"])
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].correction_type == "manual_add"


def test_post_symbol_tag_label_optional_stored_null(
    client, login, current_user_owner, owner_id, make_drawing, session_factory
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)

    body_in = _manual_body()
    body_in.pop("tag_label")
    resp = client.post(f"/drawings/{d.id}/symbols", json=body_in)
    assert resp.status_code == 201
    assert resp.json()["tag_label"] is None
    with session_factory() as s:
        assert s.get(DetectedSymbol, uuid.UUID(resp.json()["id"])).tag_label is None


def test_post_symbol_invalid_page_number_returns_422(
    client, login, current_user_owner, owner_id, make_drawing
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)

    assert (
        client.post(
            f"/drawings/{d.id}/symbols", json=_manual_body(page_number=0)
        ).status_code
        == 422
    )
    missing = _manual_body()
    missing.pop("page_number")
    assert client.post(f"/drawings/{d.id}/symbols", json=missing).status_code == 422


def test_post_symbol_invalid_entity_class_returns_422(
    client, login, current_user_owner, owner_id, make_drawing
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)
    resp = client.post(
        f"/drawings/{d.id}/symbols", json=_manual_body(entity_class_id="bogus")
    )
    assert resp.status_code == 422


def test_post_symbol_incomplete_bbox_returns_422(
    client, login, current_user_owner, owner_id, make_drawing
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)
    resp = client.post(
        f"/drawings/{d.id}/symbols",
        json=_manual_body(bbox={"x": 1.0, "y": 2.0}),  # missing w, h
    )
    assert resp.status_code == 422


def test_post_symbol_success_returns_201(
    client, login, current_user_owner, owner_id, make_drawing
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)
    resp = client.post(f"/drawings/{d.id}/symbols", json=_manual_body())
    assert resp.status_code == 201
    assert resp.json()["drawing_id"] == str(d.id)


def test_post_symbol_drawing_not_found_returns_404(
    client, login, current_user_owner
):
    login(current_user_owner)
    resp = client.post(f"/drawings/{uuid.uuid4()}/symbols", json=_manual_body())
    assert resp.status_code == 404


def test_post_symbol_wrong_owner_returns_403(
    client, login, current_user_other, owner_id, make_drawing
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_other)
    resp = client.post(f"/drawings/{d.id}/symbols", json=_manual_body())
    assert resp.status_code == 403


def test_post_symbol_unauthenticated_returns_401(
    client, owner_id, make_drawing
):
    d = make_drawing(owner_user_id=owner_id)
    resp = client.post(f"/drawings/{d.id}/symbols", json=_manual_body())
    assert resp.status_code == 401


# ===========================================================================
# US-015 — server-side training_consent snapshot
# ===========================================================================
def test_correction_snapshots_training_consent_at_creation(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    make_consent, session_factory,
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    make_consent(user_id=owner_id, opted_in=True)
    login(current_user_owner)

    client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})
    with session_factory() as s:
        from sqlalchemy import select

        c = (
            s.execute(
                select(UserCorrection).where(
                    UserCorrection.detected_symbol_id == sym.id
                )
            )
            .scalars()
            .one()
        )
    assert c.training_consent is True


def test_correction_team_consent_resolved_from_team_record(
    client, login, owner_id, make_drawing, make_symbol, make_consent,
    session_factory,
):
    team_id = uuid.uuid4()
    d = make_drawing(owner_team_id=team_id)
    sym = make_symbol(drawing_id=d.id)
    make_consent(team_id=team_id, opted_in=True)
    # A team member acting on a team-owned drawing.
    team_user = {
        "id": str(uuid.uuid4()),
        "email": "member@example.com",
        "role": "team_member",
        "team_id": str(team_id),
    }
    login(team_user)

    client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})
    with session_factory() as s:
        from sqlalchemy import select

        c = (
            s.execute(
                select(UserCorrection).where(
                    UserCorrection.detected_symbol_id == sym.id
                )
            )
            .scalars()
            .one()
        )
    assert c.training_consent is True


def test_correction_client_supplied_training_consent_ignored(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    # No consent record exists -> server resolves False, even if the client
    # tries to force True via the request body.
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    client.patch(
        f"/symbols/{sym.id}",
        json={"correction_type": "reject", "training_consent": True},
    )
    with session_factory() as s:
        from sqlalchemy import select

        c = (
            s.execute(
                select(UserCorrection).where(
                    UserCorrection.detected_symbol_id == sym.id
                )
            )
            .scalars()
            .one()
        )
    assert c.training_consent is False


def test_correction_consent_not_updated_on_later_consent_change(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    make_consent, db, session_factory,
):
    from app.db.models.ml_training_consent import MLTrainingConsent
    from sqlalchemy import select

    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    make_consent(user_id=owner_id, opted_in=False)
    login(current_user_owner)

    client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})

    # User later flips consent to True.
    consent = (
        db.execute(
            select(MLTrainingConsent).where(
                MLTrainingConsent.user_id == owner_id
            )
        )
        .scalars()
        .one()
    )
    consent.opted_in = True
    db.commit()

    with session_factory() as s:
        c = (
            s.execute(
                select(UserCorrection).where(
                    UserCorrection.detected_symbol_id == sym.id
                )
            )
            .scalars()
            .one()
        )
    assert c.training_consent is False  # snapshot, not retroactive


# ===========================================================================
# US-010 — correction_action analytics event
# ===========================================================================
def test_patch_symbol_emits_correction_action_event(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    with patch(EMIT_PATH) as mock_emit:
        resp = client.patch(
            f"/symbols/{sym.id}", json={"correction_type": "reject"}
        )
    assert resp.status_code == 200
    assert mock_emit.call_count == 1


def test_post_symbol_emits_correction_action_event(
    client, login, current_user_owner, owner_id, make_drawing
):
    d = make_drawing(owner_user_id=owner_id)
    login(current_user_owner)

    with patch(EMIT_PATH) as mock_emit:
        resp = client.post(f"/drawings/{d.id}/symbols", json=_manual_body())
    assert resp.status_code == 201
    assert mock_emit.call_count == 1


def test_correction_action_event_payload_shape(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    with patch(EMIT_PATH) as mock_emit:
        client.patch(f"/symbols/{sym.id}", json={"correction_type": "reject"})

    # Emitter is called with (user_id, drawing_id, symbol_id) — the values that
    # map onto the §1.10 {event, timestamp, user_id, drawing_id, symbol_id}.
    args, kwargs = mock_emit.call_args
    call = dict(zip(("user_id", "drawing_id", "symbol_id"), args))
    call.update(kwargs)
    assert call["user_id"] == str(owner_id)
    assert call["drawing_id"] == str(d.id)
    assert call["symbol_id"] == str(sym.id)


def test_analytics_failure_does_not_fail_response(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory,
):
    d = make_drawing(owner_user_id=owner_id)
    sym = make_symbol(drawing_id=d.id)
    login(current_user_owner)

    with patch(EMIT_PATH, side_effect=RuntimeError("posthog down")):
        resp = client.patch(
            f"/symbols/{sym.id}", json={"correction_type": "reject"}
        )
    assert resp.status_code == 200
    # The correction still persisted despite the analytics blow-up.
    with session_factory() as s:
        assert s.get(DetectedSymbol, sym.id).rejected is True


# ===========================================================================
# Technical ACs — batch query (no N+1) and single-transaction atomicity
# ===========================================================================
def test_list_symbols_uses_batch_correction_query_not_n_plus_1(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    engine, db,
):
    from sqlalchemy import event as sa_event

    d = make_drawing(owner_user_id=owner_id)
    syms = [make_symbol(drawing_id=d.id) for _ in range(5)]
    for sym in syms:
        db.add(
            UserCorrection(
                detected_symbol_id=sym.id,
                user_id=owner_id,
                correction_type="reject",
                new_class_id=None,
                training_consent=False,
            )
        )
    db.commit()
    login(current_user_owner)

    correction_selects = []

    def _count(conn, cursor, statement, params, context, executemany):
        low = statement.lower()
        if "from user_correction" in low and low.strip().startswith("select"):
            correction_selects.append(statement)

    sa_event.listen(engine, "before_cursor_execute", _count)
    try:
        body = client.get(f"/drawings/{d.id}/symbols").json()
    finally:
        sa_event.remove(engine, "before_cursor_execute", _count)

    # All five symbols' corrections returned, fetched in a single batched query
    # (not one-per-symbol) — the NFR-19 panel-open precondition.
    assert sum(len(v) for v in body["corrections_by_symbol_id"].values()) == 5
    assert len(correction_selects) <= 1


def test_correction_creates_symbol_update_correction_state_in_one_transaction(
    client, login, current_user_owner, owner_id, make_drawing, make_symbol,
    session_factory, count_corrections,
):
    # Force the state transition (the last write in the unit of work) to blow
    # up; a single-transaction implementation must roll the symbol mutation and
    # the correction insert back too — no partial persistence.
    d = make_drawing(owner_user_id=owner_id, state="Complete")
    sym = make_symbol(drawing_id=d.id, entity_class_id="valve_gate")
    login(current_user_owner)

    with patch(
        "app.services.correction_service._transition_to_under_review",
        side_effect=RuntimeError("boom"),
    ):
        resp = client.patch(
            f"/symbols/{sym.id}",
            json={"correction_type": "reclassify", "new_class_id": "valve_ball"},
        )
    assert resp.status_code == 500

    with session_factory() as s:
        assert s.get(DetectedSymbol, sym.id).entity_class_id == "valve_gate"
        assert s.get(Drawing, d.id).processing_state == "Complete"
    assert count_corrections(sym.id) == 0
