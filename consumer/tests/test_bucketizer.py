from datetime import datetime, timezone

import pytest

from bucketizer import Bucketizer, floor_to_tick
from source import RecentChangeEvent


def make_event(dt: datetime, title: str = "PageA", user: str = "u1", bot: bool = False,
               length_old: int = 100, length_new: int = 120) -> RecentChangeEvent:
    return RecentChangeEvent(
        event_type="edit",
        dt=dt,
        wiki="enwiki",
        server_name="en.wikipedia.org",
        namespace=0,
        title=title,
        user=user,
        bot=bot,
        length_old=length_old,
        length_new=length_new,
    )


def test_floor_to_tick_rounds_down():
    dt = datetime(2026, 1, 1, 12, 7, 43, tzinfo=timezone.utc)
    assert floor_to_tick(dt) == datetime(2026, 1, 1, 12, 6, 0, tzinfo=timezone.utc)


def test_floor_to_tick_on_boundary():
    dt = datetime(2026, 1, 1, 12, 6, 0, tzinfo=timezone.utc)
    assert floor_to_tick(dt) == datetime(2026, 1, 1, 12, 6, 0, tzinfo=timezone.utc)


def test_bucketizer_no_flush_within_tick():
    b = Bucketizer()
    e1 = make_event(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    e2 = make_event(datetime(2026, 1, 1, 12, 1, 30, tzinfo=timezone.utc))
    assert b.add(e1) is None
    assert b.add(e2) is None


def test_bucketizer_flushes_on_tick_change():
    b = Bucketizer()
    e1 = make_event(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    e2 = make_event(datetime(2026, 1, 1, 12, 3, 0, tzinfo=timezone.utc))

    b.add(e1)
    rows = b.add(e2)

    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["edit_count"] == 1
    assert rows[0]["byte_diff_abs_sum"] == 20


def test_bucketizer_aggregates_multiple_edits():
    b = Bucketizer()
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    b.add(make_event(t, user="u1"))
    b.add(make_event(t, user="u2", bot=True))

    rows = b.force_flush()
    assert rows[0]["edit_count"] == 2
    assert rows[0]["distinct_users"] == 2
    assert rows[0]["bot_edit_count"] == 1


def test_bucketizer_byte_diff_abs():
    b = Bucketizer()
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    b.add(make_event(t, length_old=200, length_new=100))  # diff = 100
    b.add(make_event(t, length_old=100, length_new=150))  # diff = 50

    rows = b.force_flush()
    assert rows[0]["byte_diff_abs_sum"] == 150