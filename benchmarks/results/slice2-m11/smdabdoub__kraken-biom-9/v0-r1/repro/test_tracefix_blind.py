import kraken_biom as kb


def _entry(rank, ncbi, name, taxon_reads, clade_reads, indent):
    return {"percent": "0.00", "clade_reads": str(clade_reads), "taxon_reads": str(taxon_reads), "rank": rank, "ncbi_tax": str(ncbi), "sci_name": " " * indent + name}


def test_unrelated_phylum_class_not_in_lineage():
    data = [
        _entry("D", 2759, "Eukaryota", 0, 10, 2),
        _entry("P", 3041, "Chlorophyta", 0, 1, 4),
        _entry("C", 75966, "Trebouxiophyceae", 1, 1, 6),
        _entry("-", 33682, "Euglenozoa", 0, 1, 4),
        _entry("O", 5653, "Kinetoplastida", 0, 1, 6),
        _entry("F", 5654, "Trypanosomatidae", 0, 1, 8),
        _entry("G", 5690, "Trypanosoma", 0, 1, 10),
        _entry("S", 5693, "Trypanosoma cruzi", 0, 1, 12),
    ]
    counts, taxa = kb.parse_kraken_report(data, max_rank="O", min_rank="S")
    lineage = str(taxa["5693"])
    assert "Chlorophyta" not in lineage
    assert "Trebouxiophyceae" not in lineage
