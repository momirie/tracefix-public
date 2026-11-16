from nipype.interfaces.mrtrix3.utils import Generate5tt, Generate5ttInputSpec


def test_generate5tt_has_extra_inputs():
    spec = Generate5ttInputSpec()
    names = set(spec.copyable_trait_names())
    # MRtrix3 5ttgen options beyond in_file, algorithm, out_file
    expected = {'nocrop', 'sgm_amyg_hipp', 't2_image', 'premasked'}
    missing = expected - names
    assert not missing, 'missing inputs: %s' % sorted(missing)
