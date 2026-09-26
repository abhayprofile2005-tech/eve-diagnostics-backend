from datetime import datetime, timedelta, timezone

from tests.conftest import make_centre_and_test, signup_and_login


def _future_iso(days=3):
    return (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)).isoformat()


def test_create_booking_sets_amount_from_test_price(api):
    headers = signup_and_login(api)
    _, test = make_centre_and_test(api, headers, price=750.0)

    resp = api.post(
        "/bookings/",
        json={"test_id": test["id"], "appointment_time": _future_iso()},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == 750.0
    assert body["status"] == "PENDING"


def test_booking_rejects_past_appointment_time(api):
    headers = signup_and_login(api)
    _, test = make_centre_and_test(api, headers)

    past = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)).isoformat()
    resp = api.post(
        "/bookings/", json={"test_id": test["id"], "appointment_time": past}, headers=headers
    )
    assert resp.status_code == 422


def test_booking_unknown_test_returns_404(api):
    headers = signup_and_login(api)
    resp = api.post(
        "/bookings/", json={"test_id": 9999, "appointment_time": _future_iso()}, headers=headers
    )
    assert resp.status_code == 404


def test_user_cannot_view_another_users_booking(api):
    headers_a = signup_and_login(api, email="alice@example.com")
    headers_b = signup_and_login(api, email="bob2@example.com")
    _, test = make_centre_and_test(api, headers_a)

    booking = api.post(
        "/bookings/", json={"test_id": test["id"], "appointment_time": _future_iso()}, headers=headers_a
    ).json()

    resp = api.get(f"/bookings/{booking['id']}", headers=headers_b)
    assert resp.status_code == 403


def test_get_nonexistent_booking_returns_404(api):
    headers = signup_and_login(api)
    resp = api.get("/bookings/9999", headers=headers)
    assert resp.status_code == 404


def test_cancel_pending_booking_succeeds(api):
    headers = signup_and_login(api)
    _, test = make_centre_and_test(api, headers)
    booking = api.post(
        "/bookings/", json={"test_id": test["id"], "appointment_time": _future_iso()}, headers=headers
    ).json()

    resp = api.post(f"/bookings/{booking['id']}/cancel", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_cancel_already_cancelled_booking_conflicts(api):
    headers = signup_and_login(api)
    _, test = make_centre_and_test(api, headers)
    booking = api.post(
        "/bookings/", json={"test_id": test["id"], "appointment_time": _future_iso()}, headers=headers
    ).json()

    api.post(f"/bookings/{booking['id']}/cancel", headers=headers)
    resp = api.post(f"/bookings/{booking['id']}/cancel", headers=headers)
    assert resp.status_code == 409
