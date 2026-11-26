"""Date and time utilities configured for Sri Lanka (Asia/Colombo UTC+05:30)."""

from datetime import datetime, date, timezone, timedelta
from typing import Optional

# Sri Lanka Standard Time is UTC+05:30 without Daylight Saving Time
COLOMBO_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Colombo")


def now_colombo() -> datetime:
    """Get current datetime in Asia/Colombo time zone (UTC+05:30)."""
    return datetime.now(COLOMBO_TZ)



def today_colombo() -> date:
    """Get current date in Asia/Colombo time zone."""
    return now_colombo().date()


def format_date(d: Optional[date], fmt: str = "%Y-%m-%d") -> str:
    """Format date string."""
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.strftime(fmt)
    return d.strftime(fmt)


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %I:%M %p") -> str:
    """Format timestamp with am/pm."""
    if dt is None:
        return ""
    return dt.strftime(fmt)


def parse_date(date_str: str) -> Optional[date]:
    """Parse common date formats."""
    if not date_str or not date_str.strip():
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")
