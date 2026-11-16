import kraken_biom as kb


def _entry(rank, ncbi, name, taxon=0, clade=0):
    return {"pct_reads": "0.00", "clade_reads": str(clade), "taxon_reads": str(taxon),
            "rank": rank, "ncbi_tax": str(ncbi), "sci_name": name}


def test_hierarchy_uses_indentation():
    rows = [
        _entry("D", 2759, "Eukaryota"),
        _entry("P", 3041, "  Chlorophyta"),
        _entry("C", 75966, "    Trebouxiophyceae", taxon=1, clade=1),
        _entry("-", 33682, "  Euglenozoa"),
        _entry("O", 5653, "    Kinetoplastida"),
        _entry("F", 5654, "      Trypanosomatidae"),
        _entry("G", 5690, "        Trypanosoma"),
        _entry("S", 5693, "          Trypanosoma cruzi", taxon=1, clade=1),
    ]
    counts, taxa = kb.parse_kraken_report(rows, max_rank="O", min_rank="S")
    lineage = "; ".join(taxa["5693"])
    assert "Chlorophyta" not in lineage
    assert "Trebouxiophyceae" not in lineage
    assert "Kinetoplastida" in lineage
