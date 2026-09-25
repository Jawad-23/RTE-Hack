from planner import checker

PLAN = {
    "recommended": {"setup": "wet_pad", "crop": "tomato", "capex_qar": 150000.0, "payback_years": 6.0, "coverage_pct": 100.0},
    "options": [{"setup": "chiller", "capex_qar": 826225.0, "payback_years": 30.04}],
    "reason": "wet_pad keeps the crop below its heat limit 100.0% of the year",
}


def test_made_up_payback_fails():
    ok, bad = checker.verify("A wet-pad greenhouse pays back in 3.4 years.", PLAN)
    assert not ok and 3.4 in bad


def test_plan_numbers_pass_with_rounding_and_thousands_separators():
    ok, bad = checker.verify("It costs 150,000 QAR, pays back in 6 years; a chiller would cost about 826,000 QAR.", PLAN)
    assert ok, bad


def test_arabic_indic_digits_pass():
    ok, bad = checker.verify("تكلفة الإنشاء ١٥٠٬٠٠٠ ريال وتسترد خلال ٦ سنوات.", PLAN)
    assert ok, bad


def test_arabic_made_up_number_fails():
    ok, bad = checker.verify("تسترد خلال ٣٫٤ سنوات.", PLAN)
    assert not ok and 3.4 in bad


def test_months_years_and_user_numbers_allowed():
    assert checker.verify("Plant in month 10 of 2027.", PLAN)[0]
    assert checker.verify("With 500 m² you get this plan.", PLAN, user_text="I have 500 m2")[0]


def test_numbers_inside_tool_results_are_allowed():
    ok, _ = checker.verify("With double the budget, payback is 4.2 years.", PLAN, tool_results=[{"payback_years": 4.2}])
    assert ok


def test_extract_numbers():
    assert checker.extract_numbers("1,234.5 QAR and 37°C, ٤٥") == [1234.5, 37.0, 45.0]


def test_k_and_thousand_suffixes_are_expanded():
    assert checker.extract_numbers("about 150k QAR, or 826 thousand for a chiller") == [150000.0, 826000.0]
    assert checker.verify("It costs about 150k QAR.", PLAN)[0]
    assert not checker.verify("It costs about 90k QAR.", PLAN)[0]


def test_space_grouped_thousands_are_one_number():
    assert checker.extract_numbers("costs 150 000 QAR, or 826 225 QAR, in 2 phases") == [150000.0, 826225.0, 2.0]
    assert checker.verify("A wet-pad costs 150 000 QAR.", PLAN)[0]
