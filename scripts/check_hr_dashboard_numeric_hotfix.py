from decimal import Decimal
from services.hr.service import _as_proto_int

cases = [
    (None, 0),
    (0, 0),
    (12, 12),
    (Decimal("0"), 0),
    (Decimal("37"), 37),
]
for value, expected in cases:
    actual = _as_proto_int(value)
    assert actual == expected, (value, actual, expected)
    assert isinstance(actual, int), (value, type(actual))
print("HR DASHBOARD NUMERIC HOTFIX CHECK: PASS")
