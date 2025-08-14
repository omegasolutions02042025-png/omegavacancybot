from funcs import is_russia_only_citizenship


def run_tests():
    cases = [
        ("Гражданство: РФ", True),
        ("Гражданство: Россия", True),
        ("Гражданство: только РФ", True),
        ("Гражданство: РФ и РБ", False),
        ("Гражданство: РФ/РБ", False),
        ("Гражданство: РБ или РФ", False),
        ("Гражданство: любой", False),
        ("Гражданство: любая", False),
        ("Гражданство: Беларусь", False),
        ("Гражданство: РФ\nЛокация специалиста: любая", False),

        ("Локация специалиста: РФ", True),
        ("Локация специалиста: Россия", True),
        ("Локация специалиста: любая", False),
        ("Локация специалиста: Беларусь", False),
        ("Локация специалиста: РФ, РБ", False),
        ("Локация специалиста: из РФ", True),
        ("Локация специалиста: жители РФ", True),
        ("Локация специалиста: работа из любой точки РФ", True),
        ("Гражданство: РФ\nЛокация специалиста: РБ", False),
        ("Гражданство: Россия\nЛокация специалиста: Казахстан", False),
        ("Гражданство: РФ; Локация специалиста: worldwide", False),
    ]

    total = len(cases)
    passed = 0
    for text, expected in cases:
        actual = is_russia_only_citizenship(text)
        ok = "PASS" if actual == expected else "FAIL"
        if ok == "PASS":
            passed += 1
        print(f"{ok}: expected={expected}, actual={actual} :: {text}")

    print(f"\nPassed {passed}/{total} tests")


if __name__ == "__main__":
    run_tests()


