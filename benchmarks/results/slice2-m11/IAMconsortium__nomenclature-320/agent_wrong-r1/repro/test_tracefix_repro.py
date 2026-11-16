from nomenclature.definition import DataStructureDefinition


def test_region_country_only_config(tmp_path):
    (tmp_path / "nomenclature.yaml").write_text(
        "definitions:\n  region:\n    country: true\n"
    )
    var_dir = tmp_path / "definitions" / "variable"
    var_dir.mkdir(parents=True)
    (var_dir / "var.yaml").write_text("- Primary Energy:\n    unit: EJ/yr\n")

    dsd = DataStructureDefinition(tmp_path / "definitions")

    assert "Austria" in dsd.region.mapping
    assert "Primary Energy" in dsd.variable.mapping
