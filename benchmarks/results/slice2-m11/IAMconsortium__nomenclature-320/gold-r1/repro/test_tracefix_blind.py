from nomenclature.definition import DataStructureDefinition


def test_region_only_country_config(tmp_path):
    defs = tmp_path / "definitions"
    (defs / "region").mkdir(parents=True)
    (tmp_path / "nomenclature.yaml").write_text(
        "definitions:\n  region:\n    country: true\n"
    )
    dsd = DataStructureDefinition(defs, dimensions=["region"])
    assert "Germany" in dsd.region.mapping
