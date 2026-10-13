import datetime
import zoneinfo
from urllib.parse import quote

__all__ = ("create_gcalendar_event",)


def create_gcalendar_event(
    what: str,
    times: tuple[datetime.datetime, datetime.datetime],
    *,
    details: str | None = None,
    timezone: datetime.timezone | zoneinfo.ZoneInfo | None = None,
    location: str | None = None,
) -> str:
    # https://calendar.google.com/calendar/render?action=TEMPLATE&dates=20260926T130000Z%2F20260926T160000Z&location=%5BEU%5D%20Light%20DC&text=LFG%20Forked%20Tower%3A%20Blood%203rd%20Boss%20Prog%20Run%20-%20Yuma
    ret = "https://calendar.google.com/calendar/render?action=TEMPLATE"

    # title
    ret += f"&text={quote(what)}"

    # dates
    start, end = times

    def gcal_safe(dt: datetime.datetime) -> str:
        return dt.strftime("%Y%m%d%H%M%SZ")

    ret += f"&dates={gcal_safe(start)}/{gcal_safe(end)}"
    if timezone:
        ret += f"&ctz={timezone.tzname(start)}"

    # details
    if details:
        ret += f"&details={quote(what)}"

    # location
    if location:
        ret += f"&location={quote(location)}"

    return f"[Add to Google Calendar]({ret})"
