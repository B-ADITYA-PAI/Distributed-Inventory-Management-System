"""Mock inventory catalogue and 30-day historical sales data."""

INVENTORY = {
    "item_101": {"name": "Laptop", "stock": 50},
    "item_102": {"name": "Wireless Mouse", "stock": 20},
    "item_103": {"name": "Keyboard", "stock": 35},
    "item_104": {"name": "Monitor", "stock": 30},
    "item_105": {"name": "Headphones", "stock": 25},
    "item_106": {"name": "Webcam", "stock": 25},
    "item_107": {"name": "USB-C Charger", "stock": 35},
    "item_108": {"name": "SSD", "stock": 15},
    "item_109": {"name": "Mechanical Keyboard", "stock": 30},
    "item_110": {"name": "Laptop Stand", "stock": 25},
    "item_111": {"name": "HDMI Cable", "stock": 55},
    "item_112": {"name": "Power Bank", "stock": 20},
}

# Each list contains units sold per day, oldest -> newest.
# The dataset intentionally contains different demand patterns.
MOCK_SALES_HISTORY = {
    "item_101": [4, 3, 5, 3, 5, 3, 5, 5, 3, 3, 5, 4, 4, 3, 5, 5, 4, 4, 5, 5, 3, 5, 4, 4, 4, 4, 4, 4, 3, 4],
    "item_102": [4, 3, 3, 3, 5, 5, 6, 5, 5, 4, 5, 5, 4, 6, 6, 5, 6, 6, 5, 6, 6, 7, 7, 6, 7, 6, 8, 7, 7, 6],
    "item_103": [4, 5, 6, 5, 5, 4, 5, 6, 6, 5, 4, 5, 6, 6, 6, 5, 4, 5, 5, 6, 5, 5, 5, 4, 6, 4, 4, 6, 5, 6],
    "item_104": [5, 6, 5, 5, 6, 6, 5, 5, 5, 4, 6, 4, 4, 5, 4, 4, 4, 5, 3, 3, 3, 5, 5, 5, 4, 3, 3, 3, 2, 4],
    "item_105": [9, 9, 9, 8, 5, 8, 6, 6, 2, 7, 9, 2, 2, 5, 2, 4, 3, 7, 5, 8, 5, 2, 8, 6, 5, 7, 3, 8, 6, 8],
    "item_106": [3, 3, 10, 4, 3, 3, 3, 10, 8, 3, 3, 10, 4, 8, 10, 4, 4, 3, 3, 10, 4, 8, 2, 4, 3, 3, 3, 8, 3, 3],
    "item_107": [6, 6, 7, 7, 6, 7, 7, 7, 8, 7, 7, 7, 7, 8, 9, 8, 8, 9, 7, 9, 8, 9, 9, 10, 9, 9, 9, 10, 8, 10],
    "item_108": [1, 3, 3, 2, 2, 2, 2, 2, 2, 2, 1, 1, 3, 2, 2, 2, 1, 2, 2, 1, 2, 3, 2, 1, 2, 3, 2, 2, 3, 2],
    "item_109": [4, 3, 5, 5, 5, 3, 5, 6, 4, 6, 6, 6, 5, 7, 3, 6, 8, 8, 8, 5, 5, 4, 5, 7, 6, 6, 6, 6, 5, 8],
    "item_110": [4, 4, 3, 4, 4, 4, 2, 3, 3, 3, 3, 2, 2, 3, 3, 3, 3, 4, 3, 2, 3, 2, 3, 2, 3, 2, 4, 2, 3, 4],
    "item_111": [8, 6, 7, 6, 7, 8, 7, 7, 8, 7, 8, 7, 8, 7, 7, 8, 7, 8, 7, 7, 6, 7, 7, 7, 7, 7, 7, 7, 8, 8],
    "item_112": [3, 2, 4, 4, 3, 4, 4, 4, 4, 5, 5, 4, 3, 6, 5, 4, 5, 6, 5, 4, 6, 6, 5, 5, 6, 6, 6, 6, 6, 6],
}

assert set(INVENTORY) == set(MOCK_SALES_HISTORY)
assert len(INVENTORY) == 12
assert all(len(values) == 30 for values in MOCK_SALES_HISTORY.values())
assert all(
    isinstance(value, int) and value >= 0
    for history in MOCK_SALES_HISTORY.values()
    for value in history
)


def historical_total(item_id: str) -> int:
    return sum(MOCK_SALES_HISTORY[item_id])


def recent_7_total(item_id: str) -> int:
    return sum(MOCK_SALES_HISTORY[item_id][-7:])


def average_daily(item_id: str) -> float:
    history = MOCK_SALES_HISTORY[item_id]
    return sum(history) / len(history)


def recent_7_average(item_id: str) -> float:
    return recent_7_total(item_id) / 7


def min_daily(item_id: str) -> int:
    return min(MOCK_SALES_HISTORY[item_id])


def max_daily(item_id: str) -> int:
    return max(MOCK_SALES_HISTORY[item_id])


def variability_label(item_id: str) -> str:
    history = MOCK_SALES_HISTORY[item_id]
    spread = max(history) - min(history)
    if spread >= 7:
        return "HIGH"
    if spread >= 4:
        return "MEDIUM"
    return "LOW"


def trend_label(item_id: str) -> str:
    history = MOCK_SALES_HISTORY[item_id]
    first_7 = sum(history[:7])
    last_7 = sum(history[-7:])
    difference = last_7 - first_7

    if abs(difference) <= 3:
        return "STABLE"
    if difference > 0:
        return "INCREASING"
    return "DECREASING"
