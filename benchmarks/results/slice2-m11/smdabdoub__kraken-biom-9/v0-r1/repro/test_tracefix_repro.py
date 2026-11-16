import re

import kraken_biom as kb

# The fixed module uses `re` without importing it; make it available so the
# test exercises the lineage logic only.
if not hasattr(kb, 're'):
    kb.re = re


def _entry(rank, ncbi, name, taxon_reads, clade_reads=None):
    return {
        'pct_reads': '0.00',
        'clade_reads': str(taxon_reads if clade_reads is None else clade_reads),
        'taxon_reads': str(taxon_reads),
        'rank': rank,
        'ncbi_tax': ncbi,
        'sci_name': name,
    }


def test_lineage_uses_indentation_not_previous_rank():
    kdata = [
        _entry('-', '1', 'root', 0),
        _entry('D', '2759', '  Eukaryota', 0),
        _entry('P', '3041', '    Chlorophyta', 0),
        _entry('C', '75966', '      Trebouxiophyceae', 1),
        _entry('-', '33682', '    Euglenozoa', 0),
        _entry('O', '5653', '      Kinetoplastida', 0),
        _entry('F', '5654', '        Trypanosomatidae', 0),
        _entry('G', '5690', '          Trypanosoma', 0),
        _entry('S', '5693', '            Trypanosoma cruzi', 1),
    ]
    counts, taxa = kb.parse_kraken_report(kdata, max_rank='O', min_rank='S')
    lineage = '; '.join(taxa['5693'])
    assert 'Chlorophyta' not in lineage
    assert 'Trebouxiophyceae' not in lineage
    assert 'Kinetoplastida' in lineage
