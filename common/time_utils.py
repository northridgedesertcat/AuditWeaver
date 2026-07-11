from datetime import datetime, timezone
from typing import Optional, Union


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_epoch_millis(dt: Union[datetime, int, float, str, None]) -> int:
    if dt is None:
        return int(now_utc().timestamp() * 1000)

    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    if isinstance(dt, (int, float)):
        if dt > 1e12:
            return int(dt)
        else:
            return int(dt * 1000)

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except:
            return int(now_utc().timestamp() * 1000)

    return int(now_utc().timestamp() * 1000)


def epoch_millis_now() -> int:
    return int(now_utc().timestamp() * 1000)


def format_for_filename() -> str:
    return now_utc().strftime('%Y%m%d_%H%M%S_%f')


def format_for_directory() -> tuple[str, str]:
    return (now_utc().strftime('%Y-%m-%d'), now_utc().strftime('%H'))


def utc_from_epoch_millis(epoch_ms: int) -> datetime:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
