"""Tests for item parsing functionality."""

import pytest
from backend.app.parsing import ItemParser


class TestItemParser:
    """Test cases for ItemParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ItemParser()
    
    def test_parse_simple_item_with_quantity_unit(self):
        """Test parsing item with quantity and unit."""
        result = self.parser.parse("2 lbs chicken breast")
        
        assert result.name == "chicken breast"
        assert result.quantity == 2.0
        assert result.unit == "lbs"
    
    def test_parse_item_with_decimal_quantity(self):
        """Test parsing item with decimal quantity."""
        result = self.parser.parse("1.5 kg flour")
        
        assert result.name == "flour"
        assert result.quantity == 1.5
        assert result.unit == "kg"
    
    def test_parse_item_count_only(self):
        """Test parsing item with count only."""
        result = self.parser.parse("3 bananas")
        
        assert result.name == "banana"
        assert result.quantity == 3.0
        assert result.unit == "count"
    
    def test_parse_item_no_quantity(self):
        """Test parsing item without quantity."""
        result = self.parser.parse("milk")
        
        assert result.name == "milk"
        assert result.quantity is None
        assert result.unit is None
        assert "No quantity detected" in (result.notes or "")
    
    def test_parse_item_with_package_unit(self):
        """Test parsing item with package-type unit."""
        result = self.parser.parse("1 bunch cilantro")
        
        assert result.name == "cilantro"
        assert result.quantity == 1.0
        assert result.unit == "bunch"  
    
    def test_convert_to_standard_units_weight(self):
        """Test conversion to standard weight units."""
        result = self.parser.parse("2 lbs chicken")
        
        assert result.normalized_unit == "g"
        assert abs(result.normalized_quantity - 907.185) < 1  # 2 lbs ≈ 907g

    def test_convert_to_standard_units_volume(self):
        """Test conversion to standard volume units."""
        result = self.parser.parse("1 L milk")
        
        assert result.normalized_unit == "ml"
        assert round(result.normalized_quantity,1) == 1000.0

    def test_parse_list_multiple_items(self):
        """Test parsing multiple items."""
        items = [
            "2 lbs ground beef",
            "1 gallon milk", 
            "3 tomatoes",
            "bread"
        ]
        
        results = self.parser.parse_list(items)
        
        assert len(results) == 4
        assert results[0].name == "ground beef"
        assert results[1].name == "milk"
        assert results[2].name == "tomato"
        assert results[3].name == "bread"
    
    def test_empty_item(self):
        """Test parsing empty item."""
        result = self.parser.parse("")
        assert result.name is None
        assert "Empty item text" in (result.notes or "")

    def test_canonical_name_strips_punctuation(self):
        """Canonical item name removes punctuation and casing noise."""
        result = self.parser.parse(raw_text_item="Boneless, Skinless Chicken Thighs")
        assert result.name == "boneless skinless chicken thigh"

    def test_canonical_name_removes_number_words(self):
        """Spelled-out quantities are removed from canonical name."""
        result = self.parser.parse(raw_text_item="Two Apples")
        assert result.name == "apple"

    @pytest.mark.parametrize(
        ("raw_text", "expected"),
        [
            ("Knives", "knife"),
            ("Wives", "wife"),
            ("Cacti", "cactus"),
            ("Indices", "index"),
            ("Dice", "die"),
        ],
    )
    def test_canonical_name_handles_irregular_plurals(self, raw_text, expected):
        """Difficult irregular plurals reduce to their singular canonical form."""
        result = self.parser.parse(raw_text_item=raw_text)
        assert result.name == expected



if __name__ == "__main__":
    pytest.main([__file__])
