"""Borkowski Jalali conversion, matching frontend jalaali-js (MIT).

See THIRD_PARTY_NOTICES.md. Month offsets are anchored to the original Persian
day and clamped at month end, never accumulated via Gregorian month arithmetic.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo


def today_in_tehran() -> date:
    return datetime.now(ZoneInfo("Asia/Tehran")).date()


BREAKS = [
    -61,
    9,
    38,
    199,
    426,
    686,
    756,
    818,
    1111,
    1181,
    1210,
    1635,
    2060,
    2097,
    2192,
    2262,
    2324,
    2394,
    2456,
    3178,
]


def div(a: int, b: int) -> int:
    return (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)


def mod(a: int, b: int) -> int:
    return a - div(a, b) * b


def jalcal(jy: int) -> tuple[int, int, int]:
    gy, leap_j, jp, jump = jy + 621, -14, BREAKS[0], 0
    if jy < jp or jy >= BREAKS[-1]:
        raise ValueError("سال تقویم خارج از محدوده است.")
    for jm in BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += div(jump, 33) * 8 + div(mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += div(n, 33) * 8 + div(mod(n, 33) + 3, 4)
    if mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + div(jump + 4, 33) * 33
    leap = mod(mod(n + 1, 33) - 1, 4)
    return (4 if leap == -1 else leap), gy, march


def g2d(gy: int, gm: int, gd: int) -> int:
    d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4)
    d += div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408
    return d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752


def d2g(jdn: int) -> date:
    j = 4 * jdn + 139361631
    j += div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = div(mod(j, 1461), 4) * 5 + 308
    gd, gm = div(mod(i, 153), 5) + 1, mod(div(i, 153), 12) + 1
    return date(div(j, 1461) - 100100 + div(8 - gm, 6), gm, gd)


def to_jalali(value: date) -> tuple[int, int, int]:
    jy = value.year - 621
    leap, gy, march = jalcal(jy)
    k = g2d(value.year, value.month, value.day) - g2d(gy, 3, march)
    if k >= 0:
        if k <= 185:
            return jy, 1 + div(k, 31), mod(k, 31) + 1
        k -= 186
    else:
        jy -= 1
        k += 179 + (1 if leap == 1 else 0)
    return jy, 7 + div(k, 30), mod(k, 30) + 1


def add_persian_months(value: date, offset: int) -> date:
    jy, jm, jd = to_jalali(value)
    absolute = jy * 12 + jm - 1 + offset
    year, month = absolute // 12, absolute % 12 + 1
    leap, gy, march = jalcal(year)
    length = 31 if month <= 6 else 30 if month <= 11 or leap == 0 else 29
    day = min(jd, length)
    return d2g(g2d(gy, 3, march) + (month - 1) * 31 - div(month, 7) * (month - 7) + day - 1)
