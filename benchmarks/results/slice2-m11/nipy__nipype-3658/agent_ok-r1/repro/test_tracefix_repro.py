from nipype.interfaces.mrtrix3.utils import Generate5tt


def test_generate5tt_extra_options_in_cmdline(tmp_path):
    t1 = tmp_path / 't1.nii.gz'
    t2 = tmp_path / 't2.nii.gz'
    mask = tmp_path / 'mask.nii.gz'
    for f in (t1, t2, mask):
        f.write_text('')
    g = Generate5tt()
    g.inputs.in_file = str(t1)
    g.inputs.algorithm = 'fsl'
    g.inputs.out_file = str(tmp_path / 'out.mif')
    g.inputs.t2_image = str(t2)
    g.inputs.mask_file = str(mask)
    g.inputs.premasked = True
    g.inputs.nocrop = True
    g.inputs.sgm_amyg_hipp = True
    cmd = g.cmdline
    assert '-t2 %s' % t2 in cmd
    assert '-mask %s' % mask in cmd
    assert '-premasked' in cmd
    assert '-nocrop' in cmd
    assert '-sgm_amyg_hipp' in cmd
