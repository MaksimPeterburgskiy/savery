"""Item matching pipeline tasks."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import re

import pint 
from pint import UnitRegistry


ureg = UnitRegistry()
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

# Quantity aliases
ureg.define("@alias pound = lb")
ureg.define("@alias ounce = oz")
ureg.define("@alias fluid_ounce = fl_oz")
ureg.define("@alias kilogram = kg")
ureg.define("@alias gram = g")
ureg.define("@alias liter = L")
ureg.define("@alias milliliter = ml")




@dataclass
class ParsedItem:
    original_text: str
    name: str
    quantity: float | None
    unit: str | None
    notes: str | None


class ItemParser:
    UNITS = {
        "bunch", "head", "package", "pkg", "bag", "bags", "box", "boxes", "can", "cans",
        "jar", "jars","bottle", "bottles", "loaf", "loaves", "dozen", "count", "lb", "pound", "oz", "ounce", "fl_oz",
        "fluid_ounce", "kg", "kilogram", "g", "gram","grams", "L", "liter", "ml",
        "milliliter"
    }

    QUANTITY_PATTERNS = [
        # "2 lbs chicken breast"
        r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(.+)$',
        # "2.5 lb chicken breast" 
        r'^(\d+(?:\.\d+)?)\s+([a-zA-Z]+)\s+(.+)$',
        # "chicken breast 2 lbs"
        r'^(.+?)\s+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$',
        # "2 chicken breasts"
        r'^(\d+(?:\.\d+)?)\s+(.+)$',
    ]
    def __init__(self):
        self.ureg = ureg

    def parse(self, text: str) -> ParsedItem:
        text = text.strip()
        if not text:
            return ParsedItem(
                original_text=text,
                name="",
                quantity=None,
                unit=None,
                notes="Empty item text.",
            )
    
        for pattern in self.QUANTITY_PATTERNS:
           match = re.match(pattern, text)
           if match:
               quantity, unit, name = match.groups()
               return ParsedItem(
                   original_text=text,
                   name=name,
                   quantity=float(quantity) if quantity else None,
                   unit=unit if unit else None,
                   notes="",
               )



        return ParsedItem(
            original_text=text,
            name=text,
            quantity=quantity if 'quantity' in locals() else None,
            unit=unit if 'unit' in locals() else None,
            notes="Parsing logic not yet implemented.",
        )
    
    def find_item_name():
        pass