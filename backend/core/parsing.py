"""Item matching pipeline tasks."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import re

import pint 
from pint import UnitRegistry


ureg = UnitRegistry()

# Define custom count-based units
ureg.define("bunch = 1 * count")
ureg.define("head = 1 * count") 
ureg.define("package = 1 * count")
ureg.define("pkg = 1 * package")
ureg.define("bag = 1 * count")
ureg.define("box = 1 * count")
ureg.define("can = 1 * count")
ureg.define("jar = 1 * count")
ureg.define("bottle = 1 * count")
ureg.define("loaf = 1 * count")
ureg.define("dozen = 12 * count")




@dataclass
class ParsedItem:
    original_text: str
    name: str
    quantity: float | None
    unit: str | None
    notes: str | None
    normalized_quantity: float | None
    normalized_unit: str | None


    __print__ = lambda self: f"ParsedItem(name={self.name}, quantity={self.quantity}, unit={self.unit})\nNormalized(quantity={self.normalized_quantity}, unit={self.normalized_unit})\nNotes={self.notes}"

class ItemParser:
    UNITS = {
        "bunch", "head", "package", "pkg", "bag", "bags", "box", "boxes", "can", "cans",
        "jar", "jars","bottle", "bottles", "loaf", "loaves", "dozen", "count", "lb", "lbs","pound", "pounds", "oz", "ounce", "fl_oz",
        "fluid_ounce", "kg", "kilogram", "g", "gram","grams", "L", "liter", "ml",
        "milliliter", "clove", "cloves", "slice", "slices", "piece", "pieces", "stick", "sticks",
        "cup", "cups", "tablespoon", "tablespoons", "tbsp", "teaspoon", "teaspoons", "tsp",
        "quart", "quarts", "pint", "pints", "gallon", "gallons", "l"
    }

    WORDS_TO_IGNORE = {"of"}

    def __init__(self):
        self.ureg = ureg

    def parse(self, text: str) -> ParsedItem:
        quantity = None
        unit = None
        text = text.strip()
        if not text:
            return ParsedItem(
                original_text=text,
                name="",
                quantity=None,
                unit=None,
                normalized_quantity=None,
                normalized_unit=None,
                notes="Empty item text.",
            )

        #Find quantity and unit 
        #search for number
        #once we find a number check if the next or previous word is in UNITS
        split_text = re.split(r'\s+', text)
        unit_index = -1
        original_unit = None
        quantity_index = -1
        for i, word in enumerate(split_text):
            try:
                quantity = float(word)
                quantity_index = i
                #check next word
                if i + 1 < len(split_text) and split_text[i + 1].lower() in self.UNITS:
                    unit = split_text[i + 1].lower()
                    original_unit = split_text[i + 1]
                    unit_index = i + 1
                    break
                #check previous word
                elif i - 1 >= 0 and split_text[i - 1].lower() in self.UNITS:
                    unit = split_text[i - 1].lower()
                    original_unit = split_text[i - 1]
                    unit_index = i - 1
                    break
                else:
                    unit = "count"  # Default to count if no unit found
                    break
            except ValueError:
                continue
        else:
            quantity = None
            unit = None
            notes = "No quantity detected."


        if quantity is not None and unit is None:
            print("Quantity:", quantity, "Unit:", unit)
            print("Split text before removal:", split_text)

        if quantity is not None:
            if str(float(quantity)) in split_text:
                split_text.remove(str(float(quantity)))
            elif str(int(quantity)) in split_text:
                split_text.remove(str(int(quantity)))

        if unit is not None:    
            if original_unit in split_text:
                split_text.remove(original_unit)
        print("Split text after removal:", split_text)

        name = " ".join([w for w in split_text])
        item =  ParsedItem(
            original_text=text,
            name=name.strip(),
            quantity=quantity if 'quantity' in locals() else None,
            unit=unit if 'unit' in locals() else None,
            normalized_quantity=quantity if 'quantity' in locals() else None,
            normalized_unit=unit if 'unit' in locals() else None,
            notes=notes if 'notes' in locals() else None,
        )
        print(item)
        return self.convert_to_normalized_units(item)
    


    def convert_to_normalized_units(self, item: ParsedItem) -> ParsedItem:
        if item.unit is None or item.quantity is None:
            return item
        print("Converting:", item)
        # Map our unit names to pint-compatible unit names
        UNIT_MAPPING = {
            "lbs": "pound", "lb": "pound", "pound": "pound", "pounds": "pound",
            "oz": "ounce", "ounce": "ounce", "ounces": "ounce",
            "kg": "kilogram", "kilogram": "kilogram", 
            "g": "gram", "gram": "gram", "grams": "gram",
            "L": "liter", "liter": "liter", "liters": "liter", "l": "liter",
            "ml": "milliliter", "milliliter": "milliliter",
            "fl_oz": "fluid_ounce", "fluid_ounce": "fluid_ounce",
            "cup": "cup", "cups": "cup",
            "tablespoon": "tablespoon", "tablespoons": "tablespoon", "tbsp": "tablespoon",
            "teaspoon": "teaspoon", "teaspoons": "teaspoon", "tsp": "teaspoon",
            "quart": "quart", "quarts": "quart",
            "pint": "pint", "pints": "pint", 
            "gallon": "gallon", "gallons": "gallon",
        }
        
        # Set normalized units (what we want to convert TO)
        if item.unit in ["lbs", "lb", "pound", "pounds", "oz", "ounce", "ounces", "kg", "kilogram", "g", "gram", "grams"]:
            item.normalized_unit = "g"
        elif item.unit in ["L", "liter", "liters", "l", "ml", "milliliter", "fl_oz", "fluid_ounce", "cup", "cups", "tablespoon", "tablespoons", "tbsp", "teaspoon", "teaspoons", "tsp", "quart", "quarts", "pint", "pints", "gallon", "gallons"]:
            item.normalized_unit = "ml"
        elif item.unit in ["bunch", "head", "package", "pkg", "bag", "bags", "box", "boxes", "can", "cans",
                           "jar", "jars","bottle", "bottles", "loaf", "loaves", "dozen", "count"]:    
            item.normalized_unit = "count"
        else:
            # For count-based units or unknown units, keep as-is
            item.normalized_unit = item.unit
            item.normalized_quantity = item.quantity
            return item
            
        try:
            # Convert using pint if we have a mappable unit
            pint_unit = UNIT_MAPPING.get(item.unit)
            if pint_unit:
                quantity_with_unit = self.ureg.Quantity(item.quantity, pint_unit)
                
                # Convert to normalized unit
                if item.normalized_unit == "g":
                    normalized_quantity = quantity_with_unit.to("gram").magnitude
                elif item.normalized_unit == "ml":
                    normalized_quantity = quantity_with_unit.to("milliliter").magnitude
                else:
                    normalized_quantity = item.quantity
                    
                item.normalized_quantity = normalized_quantity
            else:
                # If no mapping found, keep original values
                item.normalized_quantity = item.quantity
                item.normalized_unit = item.unit
                
        except Exception as e:
            # If conversion fails, keep original values
            item.normalized_quantity = item.quantity
            item.normalized_unit = item.unit
            if item.notes:
                item.notes += f" Conversion error: {str(e)}"
            else:
                item.notes = f"Conversion error: {str(e)}"

        return item