import pint


def test_overlaid_context_redefinitions_latest_wins():
    ureg = pint.UnitRegistry()
    c1 = pint.Context.from_lines(["@context a", "lb = 0.5 kg"])
    c2 = pint.Context.from_lines(["@context b", "lb = 0.7 kg"])
    one_src = ureg.Quantity(1, "kg")
    ureg.enable_contexts(c1)
    assert abs(one_src.to("lb").magnitude - 2.0) < 1e-9
    ureg.enable_contexts(c2)
    assert abs(one_src.to("lb").magnitude - 1 / 0.7) < 1e-9
