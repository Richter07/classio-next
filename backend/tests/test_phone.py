import pytest

from apps.accounts.phone import InvalidPhone, normalize_phone


@pytest.mark.parametrize(
    "raw",
    ["0197000000", "01 97 00 00 00", "+2290197000000", "97000000", "97 00 00 00", "+22997000000"],
)
def test_all_known_formats_give_the_same_number(raw):
    assert normalize_phone(raw) == "+2290197000000"


@pytest.mark.parametrize("raw", ["12", "", "abc", "0000000000"])
def test_invalid_numbers_are_rejected(raw):
    with pytest.raises(InvalidPhone):
        normalize_phone(raw)
