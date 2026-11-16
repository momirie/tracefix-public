from nomenclature.definition import DataStructureDefinition


def test_region_country_only_config(tmp_path):
    defs = tmp_path / "definitions"
    (defs / "variable").mkdir(parents=True)
    (defs / "variable" / "variable.yaml").write_text(
        "- Primary Energy:\n    definition: test\n    unit: EJ/yr\n"
    )
    (tmp_path / "nomenclature.yaml").write_text(
        "definitions:\n  region:\n    country: true\n"
    )
    dsd = DataStructureDefinition(defs)
    assert "Germany" in dsd.region.mapping
