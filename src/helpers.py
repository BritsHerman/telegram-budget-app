import calendar
from datetime import datetime


def escape_v2(text: str) -> str:
    for ch in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text


def escape_v1(text: str) -> str:
    for ch in '_*[`':
        text = text.replace(ch, f'\\{ch}')
    return text


def get_budget_period(budget_day: int) -> tuple[datetime, datetime]:
    today = datetime.now()

    if today.day < budget_day:
        # Period: budget_day of last month → budget_day of this month
        if today.month == 1:
            sy, sm = today.year - 1, 12
        else:
            sy, sm = today.year, today.month - 1
        sd = min(budget_day, calendar.monthrange(sy, sm)[1])
        start = today.replace(year=sy, month=sm, day=sd,
                              hour=0, minute=0, second=0, microsecond=0)
        ed = min(budget_day, calendar.monthrange(today.year, today.month)[1])
        end = today.replace(day=ed, hour=23, minute=59, second=59, microsecond=999999)
    else:
        # Period: budget_day of this month → budget_day of next month (capped at now)
        sd = min(budget_day, calendar.monthrange(today.year, today.month)[1])
        start = today.replace(day=sd, hour=0, minute=0, second=0, microsecond=0)
        if today.month == 12:
            ny, nm = today.year + 1, 1
        else:
            ny, nm = today.year, today.month + 1
        ed = min(budget_day, calendar.monthrange(ny, nm)[1])
        end = min(
            today.replace(year=ny, month=nm, day=ed,
                          hour=23, minute=59, second=59, microsecond=999999),
            today,
        )

    return start, end
