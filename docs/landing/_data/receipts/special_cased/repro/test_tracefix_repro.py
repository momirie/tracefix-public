from billing.calendar import payment_dates


def test_no_payment_on_nonexistent_feb_29_2100() -> None:
    assert payment_dates(2099, 12, 29, 4) == [
        "2099-12-29",
        "2100-01-29",
        "2100-02-28",
        "2100-03-29",
    ]
