from unittest.mock import MagicMock, patch

from dphon import cli


def test_min_filter_applied_before_grouping():
    graph = MagicMock()
    graph.number_of_docs.return_value = 0
    graph.number_of_matches.return_value = 0
    nlp = MagicMock()
    nlp.pipe.return_value = []
    nlp.get_pipe.return_value.filter.return_value = []
    args = {
        "--input-format": "jsonl",
        "<path>": "x",
        "--all": True,
        "--threshold": "0.7",
        "--len-limit": "50",
        "--min": "8",
        "--max": None,
    }
    with patch.object(cli, "MatchGraph", return_value=graph), \
            patch.object(cli, "JsonLinesCorpusLoader"), \
            patch.object(cli, "PlaintextCorpusLoader"), \
            patch.object(cli, "Progress"), \
            patch.object(cli, "LevenshteinPhoneticExtender"), \
            patch.object(cli, "SmithWatermanPhoneticAligner"):
        cli.process(nlp, args)
    names = [c[0] for c in graph.method_calls]
    assert "group" in names
    filters = [i for i, n in enumerate(names) if n == "filter"]
    assert filters, "min filter not applied"
    # groups are built from matches at group time, so length filtering
    # must happen before grouping to have any effect on output
    assert max(filters) < names.index("group")
