from unittest.mock import MagicMock, patch

from dphon import cli


class FakeMatch:
    def __init__(self, n):
        self.n = n

    def __len__(self):
        return self.n


class FakeGraph:
    last = None

    def __init__(self):
        self.matches_list = [FakeMatch(n) for n in (2, 5, 8, 10, 20)]
        self.grouped_lengths = None
        FakeGraph.last = self

    def add_doc(self, doc):
        pass

    def number_of_docs(self):
        return 0

    def number_of_matches(self):
        return len(self.matches_list)

    def filter(self, pred):
        self.matches_list = [m for m in self.matches_list if pred(m)]

    def extend(self, ext):
        pass

    def align(self, aligner):
        pass

    def group(self):
        self.grouped_lengths = sorted(len(m) for m in self.matches_list)


def test_min_max_length_filter_applied_before_grouping():
    nlp = MagicMock()
    nlp.pipe.return_value = []
    nlp.get_pipe.return_value.filter.return_value = []
    args = {
        "--input-format": "txt",
        "<path>": "x",
        "--all": True,
        "--threshold": "0.7",
        "--len-limit": "100",
        "--min": "8",
        "--max": "10",
    }
    with patch.object(cli, "MatchGraph", FakeGraph), patch.object(
        cli, "LevenshteinPhoneticExtender", MagicMock()
    ), patch.object(cli, "SmithWatermanPhoneticAligner", MagicMock()), patch.object(
        cli, "PlaintextCorpusLoader", MagicMock()
    ):
        cli.process(nlp, args)
    assert FakeGraph.last.grouped_lengths == [8, 10]
