from datetime import datetime, timedelta
from typing import Optional, List
from babel import Locale
from babel.dates import (
    parse_date as babel_parse_date, 
    format_datetime as babel_format_datetime,
)
import re

def parse_date(
    date_str: Optional[str], 
    language: str = "en",
    fallback_languages: List[str] = ["en"]
) -> Optional[datetime]:
    """
    Parse date strings in multiple languages and formats.
    
    Args:
        date_str: Date string to parse
        language: Primary language code (e.g., 'en', 'fr', 'de', 'es', 'it')
        fallback_languages: List of fallback language codes if primary fails
        
    Supports:
        - Full dates (13 April 2023, 13 avril 2023)
        - Numeric dates (13/04/2023, 2023-04-13)
        - Partial dates (April 2023, 2023)
        - Relative dates ("yesterday", "2 days ago")
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.lower().strip()
    
    # Try to parse relative dates first
    relative_dates = {
        'en': {'today': 0, 'yesterday': 1, 'tomorrow': -1},
        'es': {'hoy': 0, 'ayer': 1, 'mañana': -1},
        'fr': {"aujourd'hui": 0, 'hier': 1, 'demain': -1},
        'de': {'heute': 0, 'gestern': 1, 'morgen': -1},
        'it': {'oggi': 0, 'ieri': 1, 'domani': -1}
    }
    
    for lang in [language] + fallback_languages:
        if lang in relative_dates and date_str in relative_dates[lang]:
            days = relative_dates[lang][date_str]
            return datetime.now() + timedelta(days=days)

    # Common numeric patterns (universal across languages)
    numeric_patterns = [
        # ISO format
        (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
        # Common numeric formats
        (r'(\d{2})/(\d{2})/(\d{4})', '%d/%m/%Y'),
        (r'(\d{2})\.(\d{2})\.(\d{4})', '%d.%m.%Y'),
        # Year only
        (r'^(\d{4})$', '%Y')
    ]

    # Try numeric patterns first
    for pattern, fmt in numeric_patterns:
        if match := re.search(pattern, date_str):
            try:
                return datetime.strptime(match.group(0), fmt)
            except ValueError:
                continue

    # Try language-specific parsing
    languages_to_try = [language] + fallback_languages
    
    for lang in languages_to_try:
        try:
            locale = Locale(lang)
            
            # Get date formats for the locale
            date_patterns = [
                locale.date_formats['full'],
                locale.date_formats['long'],
                locale.date_formats['medium'],
                locale.date_formats['short']
            ]
            
            # Try each date format
            for pattern in date_patterns:
                try:
                    parsed_date = babel_parse_date(date_str, locale=locale)
                    if parsed_date:
                        return datetime.combine(parsed_date, datetime.min.time())
                except (ValueError, AttributeError):
                    continue
                    
        except (ValueError, AttributeError):
            continue

    # If all parsing attempts fail
    return None

def format_date(
    date: datetime, 
    language: str = "en",
    format_type: str = "medium"
) -> str:
    """
    Format a datetime object according to the specified language.
    
    Args:
        date: datetime object to format
        language: Language code (e.g., 'en', 'fr')
        format_type: One of 'full', 'long', 'medium', 'short'
        
    Returns:
        Formatted date string in the specified language
    """
    try:
        locale = Locale(language)
        pattern = locale.date_formats[format_type]
        formatted = babel_format_datetime(date, format=pattern, locale=locale)
        return formatted
    except (ValueError, AttributeError):
        # Fallback to ISO format
        return date.strftime("%Y-%m-%d")