"""Item parsing helpers for shopping list ingestion."""

from __future__ import annotations

import re
import sys
import unicodedata
from typing import Iterable

from dataclasses import dataclass

import inflect
import pint
from pint import UnitRegistry

from .parsing_dicts import (
    ALL_UNITS,
    COUNT_UNITS,
    FLUID_UNITS,
    IRREGULAR_PLURALS,
    NUMBER_WORDS,
    STOP_WORDS,
    UNIT_MAPPING,
    WEIGHT_UNITS,
)


ureg = UnitRegistry()
_inflector = inflect.engine()

# Define custom count-based units
ureg.define("bunch = 1 * count")
ureg.define("head = 1 * count")
ureg.define("package = 1 * count")
ureg.define("pkg = 1 * package")
ureg.define("bag = 1 * count")
ureg.define("bags = 1 * bag")
ureg.define("box = 1 * count")
ureg.define("boxes = 1 * box")
ureg.define("can = 1 * count")
ureg.define("cans = 1 * can")
ureg.define("jar = 1 * count")
ureg.define("jars = 1 * jar")
ureg.define("bottle = 1 * count")
ureg.define("bottles = 1 * bottle")
ureg.define("loaf = 1 * count")
ureg.define("loaves = 1 * loaf")
ureg.define("dozen = 12 * count")
ureg.define("pack = 1 * count")
ureg.define("packs = 1 * pack")


TOKEN_SPLIT_PATTERN = re.compile(r"\s+")
NON_ALPHANUM = re.compile(r"[^a-z0-9\s]")


@dataclass(slots=True)
class ParsedItem:
    """Structured representation of a parsed shopping list entry."""

    original_text: str
    name: str | None
    quantity: float | None
    unit: str | None
    normalized_quantity: float | None
    normalized_unit: str | None
    notes: str | None = None


def canonicalize_item_name(value: str | None) -> str | None:
    """Produce a lowercased, punctuation-free canonical item name."""

    if value is None:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = normalized.replace("&", " and ")
    normalized = NON_ALPHANUM.sub(" ", normalized)
    tokens: list[str] = []
    for token in normalized.split():
        if not token:
            continue
        if token.isdigit():
            continue
        if token in STOP_WORDS or token in NUMBER_WORDS or token in ALL_UNITS:
            continue
        tokens.append(_singularize_token(token))

    if not tokens:
        return None
    return sys.intern(" ".join(tokens))


class ItemParser:
    """Parse raw shopping list text into canonicalized structures."""

    def __init__(self) -> None:
        self.ureg = ureg

    def parse(
        self,
        text: str | None = None,
        *,
        raw_text_item: str | None = None,
        raw_text_qty: str | None = None,
    ) -> ParsedItem:
        """Parse text into canonical item components."""

        if raw_text_item is None and text is not None:
            raw_text_item = text

        combined_parts = [part.strip() for part in (raw_text_qty, raw_text_item) if part]
        combined_text = " ".join(combined_parts).strip()
        notes: list[str] = []

        if not combined_text:
            return ParsedItem(
                original_text="",
                name=None,
                quantity=None,
                unit=None,
                normalized_quantity=None,
                normalized_unit=None,
                notes="Empty item text.",
            )

        tokens = [token for token in TOKEN_SPLIT_PATTERN.split(combined_text) if token]
        quantity, unit, removal_indexes = self._extract_quantity_and_unit(tokens)
        if quantity is None and unit is None:
            notes.append("No quantity detected.")

        if unit is None and quantity is not None:
            unit = "count"

        candidate_tokens = [token for idx, token in enumerate(tokens) if idx not in removal_indexes]
        if not candidate_tokens and raw_text_item:
            candidate_tokens = [token for token in TOKEN_SPLIT_PATTERN.split(raw_text_item) if token]
        candidate_name_text = " ".join(candidate_tokens)
        canonical_name = canonicalize_item_name(candidate_name_text)

        normalized_quantity, normalized_unit = self._normalize_quantity(quantity, unit)
        parsed = ParsedItem(
            original_text=combined_text,
            name=canonical_name,
            quantity=quantity,
            unit=unit.lower() if unit else None,
            normalized_quantity=normalized_quantity,
            normalized_unit=normalized_unit,
            notes=" ".join(notes) if notes else None,
        )
        return parsed

    def parse_list(self, items: Iterable[str]) -> list[ParsedItem]:
        """Parse a list of raw item strings."""

        return [self.parse(text=item) for item in items]

    def _extract_quantity_and_unit(self, tokens: list[str]) -> tuple[float | None, str | None, set[int]]:
        quantity = None
        unit = None
        quantity_index = None
        unit_index = None

        for index, token in enumerate(tokens):
            numeric_value = self._parse_number(token)
            if numeric_value is None:
                continue
            quantity = numeric_value
            quantity_index = index

            next_unit = self._sanitize_unit(tokens[index + 1]) if index + 1 < len(tokens) else None
            prev_unit = self._sanitize_unit(tokens[index - 1]) if index - 1 >= 0 else None

            if next_unit in self._known_units():
                unit = next_unit
                unit_index = index + 1
            elif prev_unit in self._known_units():
                unit = prev_unit
                unit_index = index - 1
            break

        removal_indexes: set[int] = set()
        if quantity_index is not None:
            removal_indexes.add(quantity_index)
        if unit_index is not None:
            removal_indexes.add(unit_index)
        return quantity, unit, removal_indexes

    def _normalize_quantity(self, quantity: float | None, unit: str | None) -> tuple[float | None, str | None]:
        if quantity is None or unit is None:
            return quantity, unit

        unit_lower = unit.lower()

        if unit_lower in WEIGHT_UNITS:
            normalized_unit = "g"
        elif unit_lower in FLUID_UNITS:
            normalized_unit = "ml"
        elif unit_lower in COUNT_UNITS:
            return quantity, "count"
        else:
            return quantity, unit_lower

        pint_unit = UNIT_MAPPING.get(unit_lower)
        if not pint_unit:
            return quantity, normalized_unit

        try:
            quantity_with_unit = self.ureg.Quantity(quantity, pint_unit)
            target_unit = "gram" if normalized_unit == "g" else "milliliter"
            normalized_quantity = quantity_with_unit.to(target_unit).magnitude
        except (pint.errors.DimensionalityError, pint.errors.UndefinedUnitError):
            return quantity, unit_lower

        return round(normalized_quantity, 3), normalized_unit

    @staticmethod
    def _parse_number(token: str) -> float | None:
        cleaned = token.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            pass
        if "/" in cleaned:
            try:
                numerator, denominator = cleaned.split("/", 1)
                return float(numerator) / float(denominator)
            except ValueError:
                return None
        return None

    def _sanitize_unit(self, token: str | None) -> str | None:
        if token is None:
            return None
        lowered = NON_ALPHANUM.sub("", token.lower())
        return lowered or None

    @staticmethod
    def _known_units() -> set[str]:
        return ALL_UNITS


def _singularize_token(token: str) -> str:
    """Convert plural nouns to singular form."""

    token_lower = token.lower()
    irregular = IRREGULAR_PLURALS.get(token_lower)
    if irregular:
        return irregular

    if _looks_plural(token_lower):
        library_result = _inflector.singular_noun(token_lower)
        if library_result:
            return library_result

    if len(token_lower) > 3:
        if token_lower.endswith("ies"):
            return token_lower[:-3] + "y"
        if token_lower.endswith("ves"):
            if token_lower.endswith(("lves", "rves")):
                return token_lower[:-3] + "f"
            return token_lower[:-3] + "fe"
        if token_lower.endswith("men"):
            return token_lower[:-3] + "man"
        if token_lower.endswith(("ses", "xes", "zes", "ches", "shes", "oes")):
            return token_lower[:-2]
        if token_lower.endswith("s") and not token_lower.endswith("ss"):
            return token_lower[:-1]

    return token_lower


def _looks_plural(token: str) -> bool:
    """Decide whether a token is probably plural."""

    complex_suffixes = ("ies", "ves", "men", "xes", "zes", "ches", "shes", "oes", "ses")
    if token.endswith(complex_suffixes):
        return True
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return True
    return False
