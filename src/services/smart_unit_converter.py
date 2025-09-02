"""Smart Unit Converter for mapping user input formats to valid Airtable options."""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of a smart conversion operation."""
    original_input: str
    detected_unit_size: float
    detected_unit_type: str
    mapped_category: str
    confidence: float
    notes: str


class SmartUnitConverter:
    """Smart converter that maps various user input formats to valid Airtable field options."""
    
    def __init__(self):
        """Initialize the smart unit converter."""
        
        # Base unit field has been removed - no longer needed
        
        self.valid_categories = {
            "General", "Steel", "Electrical", "Paint", "Construction Materials", 
            "Lamps and Bulbs", "Adapters", "Toilet Items", "Plumbing", "Tools"
        }
        
        # Unit specification detection patterns (for size extraction and categorization hints)
        self.unit_patterns = {
            # Volume specifications 
            "volume": {
                "patterns": ["l", "liter", "litre", "litres", "ltr", "ltrs", "lts"],
                "category_hints": ["Paint"],
                "notes": "Volume specification detected"
            },
            
            # Area/Cross-section specifications
            "area": {
                "patterns": ["sqm", "sqmm", "sq", "square", "mm2", "cm2", "m2"],
                "category_hints": ["Electrical", "Steel"],
                "notes": "Area specification detected"
            },
            
            # Length specifications
            "length": {
                "patterns": ["m", "meter", "meters", "metre", "metres", "mm", "cm", "km"],
                "category_hints": ["Electrical", "Steel", "Construction Materials"],
                "notes": "Length specification detected"
            },
            
            # Weight specifications
            "weight": {
                "patterns": ["kg", "kgs", "kilogram", "kilograms", "ton", "tons", "tonne", "tonnes", "g", "grams"],
                "category_hints": ["Steel", "Construction Materials"],
                "notes": "Weight specification detected"
            },
            
            # Count specifications
            "count": {
                "patterns": ["piece", "pieces", "pcs", "pc", "unit", "units", "each", "ea"],
                "category_hints": [],
                "notes": "Count specification detected"
            },
            
            # Package specifications
            "package": {
                "patterns": ["bag", "bags", "sack", "sacks", "box", "boxes", "carton", "cartons", "pack", "packs"],
                "category_hints": ["Construction Materials"],
                "notes": "Package specification detected"
            },
            
            # Electrical specifications (power, voltage, current)
            "electrical": {
                "patterns": ["w", "watts", "watt", "v", "volts", "volt", "a", "amps", "amp"],
                "category_hints": ["Electrical", "Lamps and Bulbs"],
                "notes": "Electrical specification detected"
            }
        }
        
        # Category detection patterns (enhanced)
        self.category_patterns = {
            "Paint": [
                "paint", "primer", "coating", "varnish", "enamel", "lacquer",
                "white", "black", "red", "blue", "green", "yellow",
                "plascon", "dulux", "crown", "berger",
                "liter", "litre", "ltrs", "ltr", "l"  # Volume indicators for paint
            ],
            
            "Electrical": [
                "cable", "wire", "switch", "outlet", "socket", "bulb", "lamp", "light",
                "led", "fluorescent", "adapter", "connector", "fuse", "breaker",
                "sqm", "sqmm", "sq",  # Area indicators for cables
                "1.5", "2.5", "4.0", "6.0", "10.0", "16.0"  # Common cable sizes
            ],
            
            "Steel": [
                "steel", "iron", "rebar", "beam", "plate", "angle", "channel",
                "bar", "rod", "pipe", "tube", "mesh", "sheet",
                "mm", "cm"  # Thickness indicators
            ],
            
            "Construction Materials": [
                "cement", "concrete", "sand", "gravel", "stone", "brick",
                "block", "tile", "mortar", "plaster", "adhesive",
                "bag", "bags", "sack", "ton", "tons"  # Package/weight indicators
            ],
            
            "Plumbing": [
                "pipe", "fitting", "valve", "faucet", "tap", "toilet", "sink",
                "drain", "shower", "bath", "pvc", "copper", "galvanized"
            ],
            
            "Tools": [
                "hammer", "screwdriver", "wrench", "pliers", "drill", "saw",
                "level", "tape", "measure", "tool", "equipment"
            ]
        }
        
        # Common format variations and their normalizations
        self.format_normalizations = {
            # Volume variations
            "ltrs": "l", "ltr": "l", "litres": "l", "liters": "l", "liter": "l",
            
            # Area variations  
            "sqmm": "sqm", "sq": "sqm", "square": "sqm", "mm2": "sqm", "cm2": "sqm",
            
            # Length variations
            "metres": "m", "metre": "m", "meters": "m", "meter": "m",
            
            # Weight variations
            "kgs": "kg", "kilogram": "kg", "kilograms": "kg", "tonnes": "ton", "tonne": "ton",
            
            # Count variations
            "pieces": "piece", "pcs": "piece", "pc": "piece", "units": "piece", "unit": "piece",
            
            # Package variations
            "bags": "bag", "sacks": "bag", "sack": "bag", "boxes": "bag", "box": "bag",
            
            # Power/electrical specifications (treat as specifications, not unit types)
            "w": "piece", "watts": "piece", "watt": "piece", "v": "piece", "volts": "piece", "volt": "piece", "a": "piece", "amps": "piece", "amp": "piece"
        }
    
    def convert_item_specification(self, item_name: str, category_override: Optional[str] = None) -> ConversionResult:
        """
        Convert user input item specification to valid Airtable format.
        
        Args:
            item_name: Raw item name from user input
            category_override: Optional category override from user
            
        Returns:
            ConversionResult with mapped values and confidence score
        """
        try:
            # Extract numeric specifications from item name
            unit_size, raw_unit_type = self._extract_unit_specification(item_name)
            
            # Normalize the unit type
            normalized_unit_type = self._normalize_unit_type(raw_unit_type)
            
            # Detect category (use override if provided)
            if category_override:
                mapped_category = self._map_to_valid_category(category_override)
            else:
                mapped_category = self._detect_category(item_name, normalized_unit_type)
            
            # Calculate confidence score
            confidence = self._calculate_confidence(item_name, raw_unit_type, mapped_category)
            
            # Generate notes
            notes = self._generate_conversion_notes(raw_unit_type, normalized_unit_type)
            
            result = ConversionResult(
                original_input=item_name,
                detected_unit_size=unit_size,
                detected_unit_type=normalized_unit_type,
                mapped_category=mapped_category,
                confidence=confidence,
                notes=notes
            )
            
            logger.info(f"Smart conversion: '{item_name}' → size:{unit_size}, type:{normalized_unit_type}, category:{mapped_category}, confidence:{confidence:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error in smart conversion for '{item_name}': {e}")
            # Return safe defaults
            return ConversionResult(
                original_input=item_name,
                detected_unit_size=1.0,
                detected_unit_type="piece",
                mapped_category="General",
                confidence=0.3,
                notes=f"Fallback conversion due to error: {str(e)}"
            )
    
    def _extract_unit_specification(self, item_name: str) -> Tuple[float, str]:
        """Extract unit size and type from item name."""
        try:
            # Pattern to match: Number + Unit (e.g., "20l", "1.5sqm", "100m")
            unit_pattern = r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)'
            unit_matches = re.findall(unit_pattern, item_name)
            
            if unit_matches:
                # Use the first unit match found (most specific)
                unit_size_str, unit_type = unit_matches[0]
                unit_size = float(unit_size_str)
                
                if unit_size <= 0:
                    logger.warning(f"Invalid unit_size {unit_size} extracted from {item_name}")
                    return 1.0, "piece"
                
                return unit_size, unit_type.lower()
            
            # No unit specification found
            return 1.0, "piece"
            
        except Exception as e:
            logger.warning(f"Error extracting unit specification from '{item_name}': {e}")
            return 1.0, "piece"
    
    def _normalize_unit_type(self, raw_unit_type: str) -> str:
        """Normalize unit type variations to standard forms."""
        normalized = self.format_normalizations.get(raw_unit_type.lower(), raw_unit_type.lower())
        logger.debug(f"Normalized '{raw_unit_type}' → '{normalized}'")
        return normalized
    
    def _detect_unit_pattern(self, unit_type: str) -> Optional[str]:
        """Detect what type of unit specification this is (for categorization hints)."""
        
        # Check each pattern type
        for pattern_name, pattern in self.unit_patterns.items():
            if unit_type in pattern["patterns"]:
                logger.info(f"Detected '{unit_type}' as {pattern_name} specification")
                return pattern_name
        
        return None
    
    def _detect_category(self, item_name: str, unit_type: str) -> str:
        """Detect appropriate category based on item name and unit type."""
        item_lower = item_name.lower()
        
        # Score each category based on keyword matches
        category_scores = {}
        
        for category, keywords in self.category_patterns.items():
            score = 0
            for keyword in keywords:
                if keyword in item_lower:
                    # Weight keywords by specificity
                    if len(keyword) > 3:  # Longer keywords get higher weight
                        score += 2
                    else:
                        score += 1
            
            if score > 0:
                category_scores[category] = score
        
        # Return highest scoring category, or General if no matches
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            logger.info(f"Category detection: '{item_name}' → '{best_category}' (score: {category_scores[best_category]})")
            return best_category
        
        logger.info(f"No category patterns matched for '{item_name}', defaulting to 'General'")
        return "General"
    
    def _map_to_valid_category(self, category_input: str) -> str:
        """Map user category input to valid Airtable category."""
        category_lower = category_input.lower().strip()
        
        # Direct match
        for valid_category in self.valid_categories:
            if category_lower == valid_category.lower():
                return valid_category
        
        # Partial match
        for valid_category in self.valid_categories:
            if category_lower in valid_category.lower() or valid_category.lower() in category_lower:
                logger.info(f"Category mapping: '{category_input}' → '{valid_category}' (partial match)")
                return valid_category
        
        # Fallback mappings
        fallback_mappings = {
            "paint": "Paint",
            "electrical": "Electrical", 
            "electric": "Electrical",
            "steel": "Steel",
            "metal": "Steel",
            "construction": "Construction Materials",
            "building": "Construction Materials",
            "plumbing": "Plumbing",
            "tools": "Tools",
            "tool": "Tools"
        }
        
        mapped_category = fallback_mappings.get(category_lower, "General")
        logger.info(f"Category mapping: '{category_input}' → '{mapped_category}' (fallback)")
        return mapped_category
    
    def _calculate_confidence(self, item_name: str, raw_unit_type: str, mapped_category: str) -> float:
        """Calculate confidence score for the conversion."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for successful unit detection
        if raw_unit_type != "piece":  # User provided specific unit
            confidence += 0.2
        
        # Boost confidence for successful category detection
        if mapped_category != "General":
            confidence += 0.2
        
        # Boost confidence for known patterns
        item_lower = item_name.lower()
        known_patterns = ["cable", "paint", "cement", "steel", "wire", "pipe"]
        if any(pattern in item_lower for pattern in known_patterns):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _generate_conversion_notes(self, raw_unit_type: str, normalized_unit_type: str) -> str:
        """Generate human-readable notes about the conversion."""
        notes = []
        
        if raw_unit_type != normalized_unit_type:
            notes.append(f"Normalized '{raw_unit_type}' to '{normalized_unit_type}'")
        
        # Detect unit pattern for additional context
        pattern_type = self._detect_unit_pattern(normalized_unit_type)
        if pattern_type:
            notes.append(f"Detected as {pattern_type} specification")
        
        return "; ".join(notes) if notes else "Unit specification extracted successfully"


# Global instance
smart_unit_converter = SmartUnitConverter()
