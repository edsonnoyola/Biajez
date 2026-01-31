"""
Intelligent Date Parser for Natural Language
Extracts dates from user queries with high accuracy
"""

import dateparser
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import re

class SmartDateParser:
    """
    Parse natural language dates with context awareness
    """
    
    @staticmethod
    def parse_date_range(text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract check-in and check-out dates from natural language
        
        Args:
            text: User query like "hotels in Cancun Feb 10 to Feb 15"
            
        Returns:
            Tuple of (checkin_date, checkout_date) in YYYY-MM-DD format
        """
        # Common patterns
        patterns = [
            # "Feb 10 to Feb 15", "from Feb 10 to Feb 15"
            r'(?:from\s+)?(\w+\s+\d{1,2})(?:\s+to\s+|\s*-\s*)(\w+\s+\d{1,2})',
            # "10 al 15 de febrero", "del 10 al 15"
            r'(?:del\s+)?(\d{1,2})(?:\s+al\s+|\s*-\s*)(\d{1,2})(?:\s+de\s+)?(\w+)?',
            # "February 10-15", "Feb 10-15"
            r'(\w+)\s+(\d{1,2})\s*-\s*(\d{1,2})',
        ]
        
        text_lower = text.lower()
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    groups = match.groups()
                    
                    # Pattern 1: "Feb 10 to Feb 15"
                    if len(groups) == 2 and all(g for g in groups):
                        checkin = dateparser.parse(groups[0], settings={'PREFER_DATES_FROM': 'future'})
                        checkout = dateparser.parse(groups[1], settings={'PREFER_DATES_FROM': 'future'})
                        
                        if checkin and checkout:
                            return (
                                checkin.strftime('%Y-%m-%d'),
                                checkout.strftime('%Y-%m-%d')
                            )
                    
                    # Pattern 2: "del 10 al 15 de febrero"
                    elif len(groups) == 3:
                        day1, day2, month = groups
                        month = month or SmartDateParser._extract_month(text)
                        
                        if month:
                            checkin = dateparser.parse(f"{month} {day1}", settings={'PREFER_DATES_FROM': 'future'})
                            checkout = dateparser.parse(f"{month} {day2}", settings={'PREFER_DATES_FROM': 'future'})
                            
                            if checkin and checkout:
                                return (
                                    checkin.strftime('%Y-%m-%d'),
                                    checkout.strftime('%Y-%m-%d')
                                )
                    
                except Exception as e:
                    print(f"Date parsing error: {e}")
                    continue
        
        # Fallback: Try to find any two dates in the text
        return SmartDateParser._fallback_parse(text)
    
    @staticmethod
    def _extract_month(text: str) -> Optional[str]:
        """Extract month name from text"""
        months_es = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                     'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        months_en = ['january', 'february', 'march', 'april', 'may', 'june',
                     'july', 'august', 'september', 'october', 'november', 'december']
        
        text_lower = text.lower()
        for month in months_es + months_en:
            if month in text_lower:
                return month
        return None
    
    @staticmethod
    def _fallback_parse(text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Fallback parser - extract any dates found in text
        """
        # Find all potential dates
        date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # 10/02/2026
            r'\w+\s+\d{1,2},?\s*\d{4}',        # February 10, 2026
            r'\d{1,2}\s+\w+\s+\d{4}',          # 10 February 2026
        ]
        
        found_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                parsed = dateparser.parse(match, settings={'PREFER_DATES_FROM': 'future'})
                if parsed:
                    found_dates.append(parsed)
        
        if len(found_dates) >= 2:
            found_dates.sort()
            return (
                found_dates[0].strftime('%Y-%m-%d'),
                found_dates[1].strftime('%Y-%m-%d')
            )
        elif len(found_dates) == 1:
            # Single date found - assume 3 night stay
            checkin = found_dates[0]
            checkout = checkin + timedelta(days=3)
            return (
                checkin.strftime('%Y-%m-%d'),
                checkout.strftime('%Y-%m-%d')
            )
        
        # Ultimate fallback: Default dates (7 days from now, 3 night stay)
        today = datetime.now()
        checkin = today + timedelta(days=7)
        checkout = checkin + timedelta(days=3)
        
        return (
            checkin.strftime('%Y-%m-%d'),
            checkout.strftime('%Y-%m-%d')
        )
    
    @staticmethod
    def parse_single_date(text: str) -> Optional[str]:
        """
        Parse a single date from text
        
        Args:
            text: User query
            
        Returns:
            Date in YYYY-MM-DD format or None
        """
        parsed = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
        if parsed:
            return parsed.strftime('%Y-%m-%d')
        return None


# Example usage and tests
if __name__ == "__main__":
    parser = SmartDateParser()
    
    test_cases = [
        "hotels in Cancun from Feb 10 to Feb 15",
        "hotel del 10 al 15 de febrero en Madrid",
        "busca hoteles 12 al 15 marzo",
        "February 10-15 in Miami",
        "10-15 Feb cancun",
    ]
    
    print("Testing SmartDateParser:")
    for test in test_cases:
        checkin, checkout = parser.parse_date_range(test)
        print(f"\nInput: {test}")
        print(f"Check-in: {checkin}, Check-out: {checkout}")
