import pytest
from nomenclature.definition import DataStructureDefinition


def test_country_only_region_config(tmp_path):
    (tmp_path / "definitions" / "variable").mkdir(parents=True)
    (tmp_path / "definitions" / "variable" / "var.yaml").write_text(
        "- Primary Energy:\n    unit: EJ/yr\n"
    )
    (tmp_path / "nomenclature.yaml").write_text(
        "definitions:\n  region:\n    country: true\n"
    )
    dsd = DataStructureDefinition(tmp_path / "definitions")
    assert "Austria" in dsd.region.mapping
    assert "Primary Energy" in dsd.variable.mapping
