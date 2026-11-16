import pytest
from nipype.interfaces.mrtrix3 import Generate5tt


def test_generate5tt_extra_inputs(tmp_path):
    in_file = tmp_path / 'in.nii'
    in_file.write_text('x')
    mask = tmp_path / 'mask.nii'
    mask.write_text('x')
    gen = Generate5tt()
    gen.inputs.algorithm = 'fsl'
    gen.inputs.in_file = str(in_file)
    gen.inputs.out_file = 'out.mif'
    gen.inputs.mask_file = str(mask)
    gen.inputs.premasked = True
    gen.inputs.nocrop = True
    cmd = gen.cmdline
    assert '-mask %s' % mask in cmd
    assert '-premasked' in cmd
    assert '-nocrop' in cmd
