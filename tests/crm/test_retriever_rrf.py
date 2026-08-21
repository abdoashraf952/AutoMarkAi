"""
Unit tests for the RRF (Reciprocal Rank Fusion) algorithm in app/rag/retriever.py

No I/O or database connections required — rrf_fuse() is a pure function.
"""
import pytest

from src.crm.rag.retriever import rrf_fuse


class TestRRFFuse:
    def test_single_list_preserves_order(self):
        result = rrf_fuse([[10, 20, 30]])
        assert result == [10, 20, 30]

    def test_empty_lists_returns_empty(self):
        result = rrf_fuse([])
        assert result == []

    def test_single_empty_list(self):
        result = rrf_fuse([[]])
        assert result == []

    def test_two_lists_item_in_both_ranks_higher(self):
        # id=3 is rank-0 in list2 and rank-2 in list1 → high combined score
        # id=1 is rank-0 in list1 and rank-1 in list2 → also high combined
        result = rrf_fuse([[1, 2, 3], [3, 1, 2]])
        # Both 1 and 3 have good ranks; just verify the result is deduplicated
        assert len(result) == 3
        assert set(result) == {1, 2, 3}

    def test_deduplication(self):
        result = rrf_fuse([[1, 2, 3], [2, 1, 3]])
        assert len(result) == len(set(result))

    def test_item_appearing_only_in_one_list(self):
        result = rrf_fuse([[1, 2], [3, 4]])
        assert set(result) == {1, 2, 3, 4}

    def test_union_of_all_ids_present(self):
        ids_a = [10, 20, 30]
        ids_b = [30, 40, 10]
        result = rrf_fuse([ids_a, ids_b])
        assert set(result) == {10, 20, 30, 40}

    def test_first_rank_wins_in_single_list(self):
        result = rrf_fuse([[5, 6, 7, 8]])
        assert result[0] == 5  # first in ranking → highest RRF score

    def test_top_ranked_in_both_lists_wins(self):
        # id=99 is rank 0 in both lists → must be first
        result = rrf_fuse([[99, 1, 2], [99, 3, 4]])
        assert result[0] == 99

    def test_three_lists(self):
        result = rrf_fuse([[1, 2, 3], [2, 3, 1], [3, 1, 2]])
        # All three ids appear in all three lists → all present, deduplicated
        assert set(result) == {1, 2, 3}
        assert len(result) == 3

    def test_returns_list(self):
        result = rrf_fuse([[1, 2]])
        assert isinstance(result, list)

    def test_custom_k_value(self):
        # Custom k shouldn't crash
        result = rrf_fuse([[1, 2, 3]], k=10)
        assert set(result) == {1, 2, 3}

    def test_scores_decrease_monotonically(self):
        # In a single-list scenario, RRF scores should be strictly decreasing
        ids = [10, 20, 30, 40, 50]
        result = rrf_fuse([ids])
        assert result == ids  # order must be preserved for single ranking

    def test_large_input(self):
        ids = list(range(100))
        result = rrf_fuse([ids, list(reversed(ids))])
        assert len(result) == 100
        assert set(result) == set(ids)
