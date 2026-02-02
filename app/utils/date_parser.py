"""
Intelligent Date Parser for Natural Language
Extracts dates from user queries with high accuracy
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import re

# Try to import dateparser, use fallback if not available
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    DATEPARSER_AVAILABLE = False
    print("WARNING: dateparser not installed. Using basic date parsing.")

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
            # "check in 17 check out 19", "checkin 17 checkout 19"
            r'check\s*-?\s*in\s+(\d{1,2}).*?check\s*-?\s*out\s+(\d{1,2})',
            # "Feb 10 to Feb 15", "from Feb 10 to Feb 15"
            r'(?:from\s+)?(\w+\s+\d{1,2})(?:\s+to\s+|\s*-\s*)(\w+\s+\d{1,2})',
            # "10 al 15 de febrero", "del 10 al 15"
            r'(?:del\s+)?(\d{1,2})(?:\s+al\s+|\s*-\s*)(\d{1,2})(?:\s+de\s+)?(\w+)?',
            # "February 10-15", "Feb 10-15"
            r'(\w+)\s+(\d{1,2})\s*-\s*(\d{1,2})',
            # "17/02/2026" or "17-02-2026"
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
        ]
        
        text_lower = text.lower()
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text_lower)
            if match:
                try:
                    groups = match.groups()

                    # Pattern 0: "check in 17 check out 19" - just day numbers
                    if i == 0 and len(groups) == 2:
                        day1, day2 = int(groups[0]), int(groups[1])
                        today = datetime.now()
                        month = today.month
                        year = today.year

                        # If day already passed this month, use next month
                        if day1 < today.day:
                            month += 1
                            if month > 12:
                                month = 1
                                year += 1

                        try:
                            checkin = datetime(year, month, day1)
                            checkout = datetime(year, month, day2)
                            # If checkout is before checkin, checkout is next month
                            if checkout <= checkin:
                                checkout = datetime(year, month + 1 if month < 12 else 1, day2)
                                if month == 12:
                                    checkout = datetime(year + 1, 1, day2)
                            return (checkin.strftime('%Y-%m-%d'), checkout.strftime('%Y-%m-%d'))
                        except ValueError:
                            pass

                    # Pattern 1: "Feb 10 to Feb 15"
                    elif len(groups) == 2 and all(g for g in groups):
                        if DATEPARSER_AVAILABLE:
                            checkin = dateparser.parse(groups[0], settings={'PREFER_DATES_FROM': 'future'})
                            checkout = dateparser.parse(groups[1], settings={'PREFER_DATES_FROM': 'future'})
                        else:
                            checkin = SmartDateParser._basic_parse(groups[0])
                            checkout = SmartDateParser._basic_parse(groups[1])

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
                            if DATEPARSER_AVAILABLE:
                                checkin = dateparser.parse(f"{month} {day1}", settings={'PREFER_DATES_FROM': 'future'})
                                checkout = dateparser.parse(f"{month} {day2}", settings={'PREFER_DATES_FROM': 'future'})
                            else:
                                checkin = SmartDateParser._basic_parse(f"{month} {day1}")
                                checkout = SmartDateParser._basic_parse(f"{month} {day2}")

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
    def _basic_parse(text: str) -> Optional[datetime]:
        """Basic date parser without dateparser library"""
        months_map = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        text_lower = text.lower().strip()
        today = datetime.now()
        year = today.year

        # Try to extract month and day
        month_num = None
        day_num = None

        for month_name, month_val in months_map.items():
            if month_name in text_lower:
                month_num = month_val
                break

        # Find day number
        day_match = re.search(r'\b(\d{1,2})\b', text_lower)
        if day_match:
            day_num = int(day_match.group(1))

        if month_num and day_num:
            try:
                result = datetime(year, month_num, day_num)
                # If date is in the past, assume next year
                if result < today:
                    result = datetime(year + 1, month_num, day_num)
                return result
            except ValueError:
                pass

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
                if DATEPARSER_AVAILABLE:
                    parsed = dateparser.parse(match, settings={'PREFER_DATES_FROM': 'future'})
                else:
                    parsed = SmartDateParser._basic_parse(match)
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
        if DATEPARSER_AVAILABLE:
            parsed = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
        else:
            parsed = SmartDateParser._basic_parse(text)
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
