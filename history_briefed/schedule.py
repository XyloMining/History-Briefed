"""Posting slots: the next Mon/Wed/Fri at a fixed local time, DST-safe."""
import datetime as dt
from zoneinfo import ZoneInfo

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def slots(cfg, count):
    s = cfg["schedule"]
    tz = ZoneInfo(cfg["timezone"])
    wanted = {DAYS[d.lower()[:3]] for d in s["weekdays"]}
    hh, mm = (int(x) for x in s["time"].split(":"))
    day = dt.date.fromisoformat(str(s["start_date"]))
    out = []
    while len(out) < count:
        if day.weekday() in wanted:
            local = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
            out.append(local)
        day += dt.timedelta(days=1)
    return out


def iso_utc(local):
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
