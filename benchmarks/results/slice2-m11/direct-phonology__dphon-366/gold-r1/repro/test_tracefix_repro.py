from unittest.mock import MagicMock, patch

from dphon import cli


def test_min_filter_applied_before_grouping():
    graph = MagicMock()
    nlp = MagicMock()
    nlp.pipe.return_value = []
    nlp.get_pipe.return_value.filter.return_value = []
    args = {
        "--input-format": "plaintext",
        "<path>": "x",
        "--all": True,
        "--threshold": "0.7",
        "--len-limit": "50",
        "--min": "8",
        "--max": None,
    }
    with patch.object(cli, "MatchGraph", return_value=graph), patch.object(
        cli, "PlaintextCorpusLoader", MagicMock()
    ), patch.object(cli, "LevenshteinPhoneticExtender", MagicMock()), patch.object(
        cli, "SmithWatermanPhoneticAligner", MagicMock()
    ):
        cli.process(nlp, args)
    names = [c[0] for c in graph.method_calls]
    assert "filter" in names and "group" in names
    last_filter = max(i for i, n in enumerate(names) if n == "filter")
    assert last_filter < names.index("group")
