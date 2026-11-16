from ..utils import Generate5tt


def test_generate5tt_extra_options(tmp_path):
    t1 = tmp_path / 'T1.nii.gz'
    t1.write_text('x')
    t2 = tmp_path / 't2.nii.gz'
    t2.write_text('x')
    mask = tmp_path / 'mask.nii.gz'
    mask.write_text('x')
    g = Generate5tt()
    g.inputs.in_file = str(t1)
    g.inputs.algorithm = 'fsl'
    g.inputs.out_file = '5tt.mif'
    g.inputs.nocrop = True
    g.inputs.sgm_amyg_hipp = True
    g.inputs.white_stem = True
    g.inputs.premasked = True
    g.inputs.t2 = str(t2)
    g.inputs.mask = str(mask)
    cmd = g.cmdline
    for opt in ['-nocrop', '-sgm_amyg_hipp', '-white_stem', '-premasked', '-t2 ' + str(t2), '-mask ' + str(mask)]:
        assert opt in cmd
    assert cmd.startswith('5ttgen')
    assert cmd.endswith('fsl ' + str(t1) + ' 5tt.mif')
