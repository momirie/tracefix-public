import pytest
from nomenclature.codelist import RegionCodeList
from nomenclature.config import NomenclatureConfig


def test_region_codelist_country_only_config(tmp_path):
    config = NomenclatureConfig.model_validate(
        {"definitions": {"region": {"country": True}}}
    )
    path = tmp_path / "region"
    path.mkdir()
    rcl = RegionCodeList.from_directory("region", path, config)
    assert "Austria" in rcl.mapping
