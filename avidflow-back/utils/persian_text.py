"""
Persian text processing utilities for legal document analysis.

Provides functions for:
- Character normalization (Arabic to Persian)
- Digit conversion (Persian to ASCII)
- Legal reference extraction (articles, subsections, paragraphs)
- Jalali date parsing
"""
import re
from typing import List, Dict, Any

# Persian/Arabic character normalization mappings
PERSIAN_CHAR_MAP = {
    '\u064A': 'ی',  # Arabic ي → Persian ی
    '\u0643': 'ک',  # Arabic ك → Persian ک
}

# Persian to ASCII digit mapping
PERSIAN_DIGITS = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
}

def normalize_persian_text(text: str) -> str:
    """
    Normalize Persian text by replacing Arabic characters with Persian equivalents.
    
    This handles common issues where Arabic keyboard layouts insert Arabic ي (U+064A)
    instead of Persian ی, and Arabic ك (U+0643) instead of Persian ک.
    
    Args:
        text: Input text potentially containing Arabic characters
        
    Returns:
        Normalized text with Persian characters and normalized whitespace
    
    Examples:
        >>> normalize_persian_text("سلام دنيا")  # Arabic ي
        'سلام دنیا'  # Persian ی
        >>> normalize_persian_text("كتاب")  # Arabic ك
        'کتاب'  # Persian ک
    """
    for arabic_char, persian_char in PERSIAN_CHAR_MAP.items():
        text = text.replace(arabic_char, persian_char)
    
    # Normalize whitespace (multiple spaces → single space)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def convert_persian_digits(text: str) -> str:
    """
    Convert Persian/Farsi digits to ASCII digits.
    
    Useful for extracting numeric values from Persian text for processing.
    
    Args:
        text: Text containing Persian digits (۰-۹)
        
    Returns:
        Text with ASCII digits (0-9)
    
    Examples:
        >>> convert_persian_digits("سال ۱۴۰۲")
        'سال 1402'
        >>> convert_persian_digits("ماده ۲۵")
        'ماده 25'
    """
    for persian, ascii_digit in PERSIAN_DIGITS.items():
        text = text.replace(persian, ascii_digit)
    return text

def extract_dates(text: str) -> Dict[str, Any]:
    """
    Extract Jalali/Persian dates from text.
    
    Recognizes various Jalali date formats commonly used in Iranian legal documents.
    
    Formats supported:
    - 1402 (year only)
    - 1402/05 (year/month)
    - 1402/05/15 (full date)
    - Also supports - and . separators
    
    Args:
        text: Text to extract dates from
        
    Returns:
        Dictionary with:
        - 'years': List of all extracted years (int)
        - 'target_year': Most recent year found, or None if no dates
    
    Examples:
        >>> extract_dates("قانون سال ۱۴۰۲ و اصلاحیه 1401/12/15")
        {'years': [1402, 1401], 'target_year': 1401}
    """
    # Convert Persian digits first
    text = convert_persian_digits(text)
    
    # Regex for Jalali dates (13XX or 14XX century)
    # Matches: YYYY, YYYY/MM, YYYY/MM/DD with various separators
    pattern = r'(?:(13|14)\d{2})(?:[\/\-\.](?:0[1-9]|1[0-2]))?(?:[\/\-\.](?:0[1-9]|[12]\d|3[01]))?'
    
    years = []
    
    for match in re.finditer(pattern, text):
        full_match = match.group(0)
        year = int(full_match[:4])
        years.append(year)
    
    # Most recent (last mentioned) year is often the target
    target_year = years[-1] if years else None
    
    return {
        "years": years,
        "target_year": target_year
    }

def extract_articles(text: str) -> List[str]:
    """
    Extract article numbers from Persian legal text.
    
    Looks for patterns like:
    - "ماده ۲۵"
    - "مادهٔ 30"
    - "ماده  ۱۵" (extra whitespace)
    
    Args:
        text: Legal document text
        
    Returns:
        List of article numbers as ASCII strings
    
    Examples:
        >>> extract_articles("طبق ماده ۲۵ و مادهٔ ۳۰")
        ['25', '30']
    """
    text = convert_persian_digits(text)
    
    # Pattern for "ماده" followed by optional ٔ and number
    pattern = r'(?:ماده|مادهٔ)\s+([۰-۹0-9]+)'
    matches = re.findall(pattern, text)
    
    # Ensure all are ASCII
    return [convert_persian_digits(m) for m in matches]

def extract_subsections(text: str) -> List[str]:
    """
    Extract subsection (تبصره) numbers from Persian legal text.
    
    Subsections (تبصره) are explanatory notes or exceptions to articles.
    
    Args:
        text: Legal document text
        
    Returns:
        List of subsection numbers as ASCII strings
    
    Examples:
        >>> extract_subsections("تبصره ۱ و تبصره 2")
        ['1', '2']
    """
    text = convert_persian_digits(text)
    
    pattern = r'تبصره\s+([۰-۹0-9]+)'
    matches = re.findall(pattern, text)
    
    return [convert_persian_digits(m) for m in matches]

def extract_paragraphs(text: str) -> List[str]:
    """
    Extract paragraph (بند) identifiers from Persian legal text.
    
    Paragraphs (بند) can be identified by:
    - Persian letters: الف، ب، پ، ت، etc.
    - Latin letters: a, b, c
    - Numbers: 1, 2, 3
    
    Args:
        text: Legal document text
        
    Returns:
        List of paragraph identifiers (strings)
    
    Examples:
        >>> extract_paragraphs("بند الف و بند (ب) و بند 1")
        ['الف', 'ب', '1']
    """
    # Pattern matches "بند" followed by optional parentheses and identifier
    pattern = r'بند\s+\(?([الف-یA-Za-z0-9]+)\)?'
    matches = re.findall(pattern, text)
    
    return matches

def process_text(
    text: str,
    operations: List[str]
) -> Dict[str, Any]:
    """
    Process Persian text with multiple operations.
    
    Args:
        text: Input text
        operations: List of operation codes:
            - 'normalize': Character normalization
            - 'digits': Digit conversion
            - 'dates': Date extraction
            - 'articles': Article extraction
            - 'subsections': Subsection extraction
            - 'paragraphs': Paragraph extraction
            - 'all': All operations
    
    Returns:
        Dictionary with processed text and extracted data
    """
    result = {
        "originalText": text,
        "processedText": text
    }
    
    if "all" in operations or "normalize" in operations:
        result["processedText"] = normalize_persian_text(result["processedText"])
    
    if "all" in operations or "digits" in operations:
        result["processedText"] = convert_persian_digits(result["processedText"])
    
    if "all" in operations or "dates" in operations:
        date_info = extract_dates(result["processedText"])
        result["dates"] = date_info
    
    if "all" in operations or "articles" in operations:
        articles = extract_articles(result["processedText"])
        result["articles"] = articles
    
    if "all" in operations or "subsections" in operations:
        subsections = extract_subsections(result["processedText"])
        result["subsections"] = subsections
    
    if "all" in operations or "paragraphs" in operations:
        paragraphs = extract_paragraphs(result["processedText"])
        result["paragraphs"] = paragraphs
    
    return result
