from arta import RulesEngine


def my_action(**kwargs):
    return {"is_bla": kwargs.get("my_arg_foo") == "some string"}


def test_extra_kwargs_forwarded_to_action(tmp_path):
    cfg = tmp_path / "rules"
    cfg.mkdir()
    (cfg / "rules.yaml").write_text(
        """
rs:
  g:
    - id: r1
      conditions:
        all:
          - field: x
            operator: equal
            value: 1
      action: my_action
"""
    )
    eng = RulesEngine(config_path=str(cfg))
    eng._action_functions = None
    res = eng.apply_rules(input_data={"x": 1}, rule_set="rs", my_arg_foo="some string")
    assert res["g"] == {"is_bla": True}
