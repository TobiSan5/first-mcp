#!/usr/bin/env python3
"""
Data Processing Layer Tests — Embeddings

Tests the embeddings.py module at the data layer:
- cosine_similarity (pure math, no API required)
- weighted_combine_embeddings (pure math, no API required)
- compute_text_similarity graceful error handling when API unavailable
- rank_texts_by_similarity graceful error handling when API unavailable
"""

import os
import sys
import unittest
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestCosineSimilarity(unittest.TestCase):
    """Test cosine_similarity with known vectors."""

    def setUp(self):
        from first_mcp.embeddings import cosine_similarity
        self.cosine_similarity = cosine_similarity

    def test_identical_vectors(self):
        """Identical vectors should yield similarity of 1.0."""
        vec = [1.0, 0.5, 0.25, 0.75]
        result = self.cosine_similarity(vec, vec)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should yield similarity of 0.0."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        result = self.cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_opposite_vectors_clamped(self):
        """Opposite vectors yield raw cosine of -1 but result is clamped to 0.0."""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        result = self.cosine_similarity(vec1, vec2)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_known_similarity(self):
        """Verify a known cosine similarity by hand."""
        # vec1=[1,0], vec2=[1,1] -> cos = 1/sqrt(2) ≈ 0.7071
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 1.0]
        result = self.cosine_similarity(vec1, vec2)
        expected = 1.0 / math.sqrt(2)
        self.assertAlmostEqual(result, expected, places=5)

    def test_empty_vectors_return_zero(self):
        """Empty vectors should return 0.0 without error."""
        result = self.cosine_similarity([], [])
        self.assertEqual(result, 0.0)

    def test_one_empty_vector(self):
        """One empty vector should return 0.0."""
        result = self.cosine_similarity([1.0, 0.5], [])
        self.assertEqual(result, 0.0)

    def test_result_always_in_range(self):
        """Result must always be in [0.0, 1.0]."""
        import random
        random.seed(42)
        for _ in range(20):
            v1 = [random.uniform(-1, 1) for _ in range(8)]
            v2 = [random.uniform(-1, 1) for _ in range(8)]
            result = self.cosine_similarity(v1, v2)
            self.assertGreaterEqual(result, 0.0)
            self.assertLessEqual(result, 1.0)


class TestWeightedCombineEmbeddings(unittest.TestCase):
    """Test weighted_combine_embeddings with known vectors."""

    def setUp(self):
        from first_mcp.embeddings import weighted_combine_embeddings
        self.combine = weighted_combine_embeddings

    def test_returns_list(self):
        """Result should be a list of floats."""
        primary = [1.0, 0.0]
        context = [0.0, 1.0]
        result = self.combine(primary, context, 0.7, 0.3)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_result_is_unit_normalized(self):
        """Result vector should have L2 norm of 1.0."""
        primary = [3.0, 4.0]
        context = [1.0, 0.0]
        result = self.combine(primary, context, 0.7, 0.3)
        norm = math.sqrt(sum(x ** 2 for x in result))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_weight_zero_context_equals_primary(self):
        """Zero context weight should give same direction as primary."""
        from first_mcp.embeddings import cosine_similarity
        primary = [3.0, 4.0]
        context = [1.0, 0.0]
        result = self.combine(primary, context, 1.0, 0.0)
        # Normalised primary: [0.6, 0.8]
        norm = math.sqrt(3.0 ** 2 + 4.0 ** 2)
        normalised_primary = [3.0 / norm, 4.0 / norm]
        sim = cosine_similarity(result, normalised_primary)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_weight_ratio_matters_not_magnitude(self):
        """Doubling both weights should yield the same result (direction only)."""
        from first_mcp.embeddings import cosine_similarity
        primary = [1.0, 2.0]
        context = [3.0, 1.0]
        r1 = self.combine(primary, context, 0.7, 0.3)
        r2 = self.combine(primary, context, 7.0, 3.0)
        sim = cosine_similarity(r1, r2)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_empty_vectors_return_none(self):
        """Empty vectors should return None gracefully."""
        result = self.combine([], [], 0.7, 0.3)
        self.assertIsNone(result)


class TestComputeTextSimilarityNoApi(unittest.TestCase):
    """
    Test compute_text_similarity behaviour when the embedding API is unavailable.
    These tests do not require a live API key.
    """

    def setUp(self):
        from first_mcp.embeddings import compute_text_similarity
        self.compute = compute_text_similarity
        # Stash and clear the API key so tests run without real API calls
        self._original_key = os.environ.get('GOOGLE_API_KEY')
        os.environ.pop('GOOGLE_API_KEY', None)

    def tearDown(self):
        if self._original_key is not None:
            os.environ['GOOGLE_API_KEY'] = self._original_key
        else:
            os.environ.pop('GOOGLE_API_KEY', None)

    def test_returns_dict(self):
        """Should always return a dict."""
        result = self.compute("hello", "world")
        self.assertIsInstance(result, dict)

    def test_no_api_key_reports_unavailable(self):
        """Without API key, api_available should be False."""
        result = self.compute("hello", "world")
        self.assertFalse(result.get('api_available'))

    def test_no_api_key_success_false(self):
        """Without API key, success should be False."""
        result = self.compute("hello", "world")
        self.assertFalse(result.get('success'))

    def test_no_api_key_error_message_present(self):
        """Without API key, an error message should be present."""
        result = self.compute("hello", "world")
        self.assertIn('error', result)
        self.assertIsInstance(result['error'], str)
        self.assertGreater(len(result['error']), 0)

    def test_context_parameter_accepted(self):
        """Context parameter should be accepted without raising an exception."""
        result = self.compute(
            "grace_follows_faith",
            "For by grace you have been saved through faith.",
            context="Paul writes to the Ephesians about salvation.",
            text_weight=0.7,
            context_weight=0.3
        )
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get('success'))


class TestRankTextsBySimilarityNoApi(unittest.TestCase):
    """
    Test rank_texts_by_similarity behaviour when the embedding API is unavailable.
    """

    def setUp(self):
        from first_mcp.embeddings import rank_texts_by_similarity
        self.rank = rank_texts_by_similarity
        self._original_key = os.environ.get('GOOGLE_API_KEY')
        os.environ.pop('GOOGLE_API_KEY', None)

    def tearDown(self):
        if self._original_key is not None:
            os.environ['GOOGLE_API_KEY'] = self._original_key
        else:
            os.environ.pop('GOOGLE_API_KEY', None)

    def test_returns_dict(self):
        """Should always return a dict."""
        result = self.rank("query", ["text one", "text two"])
        self.assertIsInstance(result, dict)

    def test_no_api_key_success_false(self):
        """Without API key, success should be False."""
        result = self.rank("query", ["text one", "text two"])
        self.assertFalse(result.get('success'))

    def test_empty_candidates_error(self):
        """Empty candidates list should return an error regardless of API."""
        result = self.rank("query", [])
        self.assertFalse(result.get('success'))
        self.assertIn('error', result)


if __name__ == '__main__':
    print("⚙️  Data Processing Layer Tests — Embeddings")
    print("Math tests run without API; API-dependent tests verify graceful failure.")
    unittest.main(verbosity=2)
