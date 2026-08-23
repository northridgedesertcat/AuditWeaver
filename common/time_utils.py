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


def parse_time_range(time_range: str = '24h') -> tuple[int, int]:
    """将形如 15m / 1h / 24h / 7d / all 的范围解析为 (gte_epoch_millis, lte_epoch_millis)。

    - lte 永远是当前 UTC 毫秒。
    - all 或无法识别时 gte=0(查全部)。
    """
    lte = epoch_millis_now()
    if not time_range:
        return 0, lte

    key = time_range.strip().lower()
    if key in ('all', '*'):
        return 0, lte

    import re
    m = re.fullmatch(r'(\d+)\s*([smhd])', key)
    if not m:
        # 不可识别时退化为查全部,避免误判成 0 条
        return 0, lte

    value = int(m.group(1))
    unit = m.group(2)
    multipliers = {'s': 1000, 'm': 60_000, 'h': 3_600_000, 'd': 86_400_000}
    delta_ms = value * multipliers[unit]
    return lte - delta_ms, lte
