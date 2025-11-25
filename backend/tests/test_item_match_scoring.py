"""Unit tests for item match candidate scoring functions."""

from __future__ import annotations

import pytest
from pytest import approx

from backend.workers.tasks import item_matches
from backend.workers.tasks.item_matches import (
    calculate_match_score,
    remove_brand_from_name,
    should_exclude_brand,
)


class TestShouldExcludeBrand:
    """Tests for should_exclude_brand function."""

    def test_no_brand_returns_false(self) -> None:
        """Should return False when no brand is provided."""
        assert should_exclude_brand(["cream", "cheese"], None) is False

    def test_direct_term_overlap_returns_false(self) -> None:
        """Should return False when user searches for the brand directly."""
        assert should_exclude_brand(["philadelphia"], "Philadelphia") is False
        assert should_exclude_brand(["kleenex"], "Kleenex") is False

    def test_no_overlap_returns_true(self) -> None:
        """Should return True when user's search doesn't include the brand."""
        assert should_exclude_brand(["cream", "cheese"], "Philadelphia") is True
        assert should_exclude_brand(["tissues"], "Kleenex") is True

    def test_hyphenated_brand_direct_match(self) -> None:
        """Should handle hyphenated brands like Band-Aid."""
        # "band" is in canon_terms, matches "band" from "Band-Aid"
        assert should_exclude_brand(["band", "aid"], "Band-Aid") is False

    def test_hyphenated_brand_compound_term(self) -> None:
        """Should handle compound searches like 'bandaid' for 'Band-Aid'."""
        # "bandaid" should match "bandaid" (brand_normalized.replace(" ", ""))
        assert should_exclude_brand(["bandaid"], "Band-Aid") is False

    def test_partial_brand_in_search(self) -> None:
        """Should detect when brand term appears in search."""
        assert should_exclude_brand(["philadelphia", "cream", "cheese"], "Philadelphia") is False

    def test_brand_with_apostrophe(self) -> None:
        """Should handle brands with apostrophes."""
        assert should_exclude_brand(["mcdonalds"], "McDonald's") is False
        assert should_exclude_brand(["burger"], "McDonald's") is True


class TestRemoveBrandFromName:
    """Tests for remove_brand_from_name function."""

    def test_no_brand_returns_original(self) -> None:
        """Should return original name when no brand provided."""
        assert remove_brand_from_name("Cream Cheese", None) == "Cream Cheese"

    def test_removes_brand_prefix(self) -> None:
        """Should remove brand from start of product name."""
        assert remove_brand_from_name("Philadelphia Cream Cheese", "Philadelphia") == "Cream Cheese"
        assert remove_brand_from_name("Kleenex Tissues", "Kleenex") == "Tissues"

    def test_case_insensitive_removal(self) -> None:
        """Should remove brand case-insensitively."""
        assert remove_brand_from_name("PHILADELPHIA Cream Cheese", "Philadelphia") == "Cream Cheese"
        assert remove_brand_from_name("philadelphia cream cheese", "Philadelphia") == "cream cheese"

    def test_brand_not_at_start_unchanged(self) -> None:
        """Should not remove brand if not at start of name."""
        assert remove_brand_from_name("Store Brand Philadelphia Style", "Philadelphia") == "Store Brand Philadelphia Style"


class TestCalculateMatchScore:
    """Tests for calculate_match_score function."""

    def test_basic_exact_match(self) -> None:
        """Exact term match should score 100."""
        score = calculate_match_score(["cream", "cheese"], "Cream Cheese")
        assert score == approx(100.0)

    def test_extra_terms_penalty(self) -> None:
        """Extra terms in product name should reduce score."""
        score = calculate_match_score(["cream", "cheese"], "Cream Cheese Spread")
        assert score < 100.0

    def test_brand_exclusion_gives_perfect_score(self) -> None:
        """Generic search with brand exclusion should score 100."""
        score = calculate_match_score(["cream", "cheese"], "Philadelphia Cream Cheese", product_brand="Philadelphia")
        assert score == approx(100.0)

    def test_brand_exclusion_multiple_brands(self) -> None:
        """Brand exclusion should work for various brands."""
        score = calculate_match_score(["cream", "cheese"], "Hannaford Cream Cheese", product_brand="Hannaford")
        assert score == approx(100.0)

    def test_user_brand_search_keeps_brand(self) -> None:
        """When user searches for brand, brand should be kept in scoring."""
        score = calculate_match_score(["philadelphia", "cream", "cheese"], "Philadelphia Cream Cheese", product_brand="Philadelphia")
        assert score == approx(100.0)

    def test_position_weighting_prefers_early_matches(self) -> None:
        """Matches in earlier positions should score higher."""
        # "Cream Cheese Spread" matches at positions 0, 1
        # "Organic Cream Cheese" matches at positions 1, 2
        score_early = calculate_match_score(["cream", "cheese"], "Cream Cheese Spread")
        score_late = calculate_match_score(["cream", "cheese"], "Organic Cream Cheese")
        assert score_early > score_late

    def test_genericized_trademark_kleenex(self) -> None:
        """User searching 'kleenex' should keep brand in scoring."""
        score = calculate_match_score(["kleenex"], "Kleenex Tissues", product_brand="Kleenex")
        # Brand NOT excluded, so "kleenex" matches position 0 only
        # Total weight: 1.0 + 0.9 = 1.9
        # Matched weight: 1.0 (position 0)
        # Score: 1.0 / 1.9 * 100 ≈ 52.63
        assert score < 60.0
        assert score > 40.0

    def test_generic_search_excludes_brand(self) -> None:
        """User searching 'tissues' should exclude brand for perfect match."""
        score = calculate_match_score(["tissues"], "Kleenex Tissues", product_brand="Kleenex")
        # Brand excluded, left with "Tissues"
        assert score == approx(100.0)

    def test_empty_product_name_returns_zero(self) -> None:
        """Empty product name should return 0."""
        score = calculate_match_score(["cream", "cheese"], "")
        assert score == approx(0.0)

    def test_green_onion_exact_match(self) -> None:
        """Green onion exact match should score 100."""
        score = calculate_match_score(["green", "onion"], "Green Onion")
        assert score == approx(100.0)

    def test_green_onion_with_organic_prefix(self) -> None:
        """Organic prefix should reduce score for 'green onion' search."""
        score = calculate_match_score(["green", "onion"], "Organic Green Onion")
        assert score < 100.0

    def test_organic_green_onion_exact_match(self) -> None:
        """Organic green onion exact match should score 100."""
        score = calculate_match_score(["organic", "green", "onion"], "Organic Green Onion")
        assert score == approx(100.0)


class TestCalculateMatchScoreWithFlagsDisabled:
    """Tests for calculate_match_score with feature flags disabled."""

    def test_brand_exclusion_disabled(self) -> None:
        """With brand exclusion disabled, brand should reduce score."""
        original_flag = item_matches.ENABLE_BRAND_EXCLUSION
        try:
            item_matches.ENABLE_BRAND_EXCLUSION = False
            score = calculate_match_score(["cream", "cheese"], "Philadelphia Cream Cheese", product_brand="Philadelphia")
            assert score < 100.0
        finally:
            item_matches.ENABLE_BRAND_EXCLUSION = original_flag

    def test_position_weighting_disabled(self) -> None:
        """With position weighting disabled, use simple term coverage."""
        original_flag = item_matches.ENABLE_POSITION_WEIGHTING
        try:
            item_matches.ENABLE_POSITION_WEIGHTING = False
            # 2 terms match out of 3 product terms = 2/3 * 100 = 66.67
            score = calculate_match_score(["cream", "cheese"], "Cream Cheese Spread")
            assert score == approx(66.67)
        finally:
            item_matches.ENABLE_POSITION_WEIGHTING = original_flag

    def test_both_flags_disabled_simple_coverage(self) -> None:
        """With both flags disabled, use simple term coverage without brand exclusion."""
        original_brand = item_matches.ENABLE_BRAND_EXCLUSION
        original_position = item_matches.ENABLE_POSITION_WEIGHTING
        try:
            item_matches.ENABLE_BRAND_EXCLUSION = False
            item_matches.ENABLE_POSITION_WEIGHTING = False
            # 2 terms match out of 3 product terms = 2/3 * 100 = 66.67
            score = calculate_match_score(["cream", "cheese"], "Philadelphia Cream Cheese", product_brand="Philadelphia")
            assert score == approx(66.67)
        finally:
            item_matches.ENABLE_BRAND_EXCLUSION = original_brand
            item_matches.ENABLE_POSITION_WEIGHTING = original_position


class TestEdgeCases:
    """Tests for edge cases in scoring."""

    def test_single_term_search(self) -> None:
        """Single term search should work correctly."""
        score = calculate_match_score(["milk"], "Milk")
        assert score == approx(100.0)

    def test_many_product_terms(self) -> None:
        """Products with many terms should be handled correctly."""
        score = calculate_match_score(["cream", "cheese"], "Philadelphia Original Whipped Cream Cheese Spread")
        # Brand excluded, left with "Original Whipped Cream Cheese Spread" (5 terms)
        # Matches at positions 2, 3 (cream, cheese)
        assert score < 100.0
        assert score > 0.0

    def test_parenthetical_in_product_name(self) -> None:
        """Products with parentheticals should be handled."""
        score = calculate_match_score(["green", "onion"], "Green Onion (Hannaford)", product_brand="Hannaford")
        # Brand "Hannaford" is in parentheses, not at start - won't be removed
        # But brand exclusion check will still see no overlap, so it's fine
        # Product terms: ["green", "onion", "(hannaford)"]
        # Matches: positions 0, 1
        assert score > 0.0

    def test_case_insensitive_matching(self) -> None:
        """Matching should be case insensitive."""
        score1 = calculate_match_score(["cream", "cheese"], "CREAM CHEESE")
        score2 = calculate_match_score(["CREAM", "CHEESE"], "cream cheese")
        assert score1 == approx(100.0)
        assert score2 == approx(100.0)
