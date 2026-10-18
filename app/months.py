"""Month helpers. Months are strings like '2026-03'. Index 0 is START."""
START = (2024, 10)
N_MONTHS = 24


def label(i: int) -> str:
    y, m = START
    total = (m - 1) + i
    return f"{y + total // 12}-{total % 12 + 1:02d}"


MONTHS = [label(i) for i in range(N_MONTHS)]


def idx(month: str) -> int:
    y, m = int(month[:4]), int(month[5:7])
    return (y - START[0]) * 12 + (m - START[1])


def shift(month: str, k: int) -> str:
    return label(idx(month) + k)
