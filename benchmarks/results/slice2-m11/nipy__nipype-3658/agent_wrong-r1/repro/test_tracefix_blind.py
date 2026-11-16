from ..utils import Generate5tt


def test_generate5tt_has_extra_mrtrix_options():
    inputs = Generate5tt.input_spec()
    names = set(inputs.copyable_trait_names())
    # Options from MRtrix3 5ttgen
    expected = {"t2_image", "mask", "premasked", "nocrop", "sgm_amyg_hipp", "lut_file"}
    missing = expected - names
    assert not missing, "Missing inputs: %s" % sorted(missing)
