"""
Unit tests for article transformation and field extraction utilities
in cron/faq_kb_sync.py (Task 1.3).
"""
import sys
import os

# Add cron directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from faq_kb_sync import (
    extract_keywords,
    truncate_text,
    categorize_article,
    generate_summary,
    generate_article_id,
)


# ─────────────────────────────────────────────────────────────────────────────
# Tests for extract_keywords
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_keywords_basic():
    result = extract_keywords("Dog Training Tips", "Learn how to train your puppy")
    keywords = result.split(",")
    assert len(keywords) <= 10
    assert all(k.isalpha() and k.islower() for k in keywords)
    assert "dog" in keywords
    assert "training" in keywords
    assert "tips" in keywords


def test_extract_keywords_removes_stop_words():
    result = extract_keywords("The Best Food for Dogs", "What is the best diet for your pet")
    keywords = result.split(",")
    # Stop words like "the", "for", "is", "what" should not appear
    assert "the" not in keywords
    assert "for" not in keywords
    assert "is" not in keywords
    assert "what" not in keywords


def test_extract_keywords_max_10():
    long_title = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
    result = extract_keywords(long_title, "more unique terms here zulu")
    keywords = result.split(",")
    assert len(keywords) <= 10


def test_extract_keywords_unique():
    result = extract_keywords("dog dog dog", "dog cat dog cat")
    keywords = result.split(",")
    # Should not have duplicates
    assert len(keywords) == len(set(keywords))


def test_extract_keywords_empty_input():
    result = extract_keywords("", "")
    assert result == ""


# ─────────────────────────────────────────────────────────────────────────────
# Tests for truncate_text
# ─────────────────────────────────────────────────────────────────────────────

def test_truncate_text_strips_html():
    html = "<p>Hello <strong>world</strong></p>"
    result = truncate_text(html)
    assert "<" not in result
    assert ">" not in result
    assert "Hello world" in result


def test_truncate_text_respects_max_chars():
    html = "<p>" + "word " * 500 + "</p>"
    result = truncate_text(html, max_chars=100)
    assert len(result) <= 100


def test_truncate_text_word_boundary():
    # "abcde fghij" with max_chars=8 should truncate to "abcde" (not "abcde fg")
    result = truncate_text("abcde fghij klmno", max_chars=8)
    assert result == "abcde"
    assert not result.endswith(" ")


def test_truncate_text_short_input_unchanged():
    html = "<b>Short text</b>"
    result = truncate_text(html)
    assert result == "Short text"


def test_truncate_text_empty_input():
    assert truncate_text("") == ""
    assert truncate_text(None) == ""


def test_truncate_text_no_html_in_output():
    html = """
    <html><body>
    <h1>Title</h1>
    <p>Paragraph with <a href="http://example.com">a link</a> and <em>emphasis</em>.</p>
    <script>alert('xss')</script>
    <style>.foo { color: red; }</style>
    </body></html>
    """
    result = truncate_text(html)
    assert "<" not in result
    assert ">" not in result
    assert "script" not in result.lower() or "alert" not in result


# ─────────────────────────────────────────────────────────────────────────────
# Tests for categorize_article
# ─────────────────────────────────────────────────────────────────────────────

def test_categorize_nutrition():
    assert categorize_article("Best Dog Food Brands", "Which diet works best") == "nutrition"


def test_categorize_training():
    assert categorize_article("Obedience Training 101", "Teach your dog basic commands") == "training"


def test_categorize_health():
    assert categorize_article("Common Cat Diseases", "Symptoms to watch for") == "health"


def test_categorize_behavior():
    assert categorize_article("Dealing with Aggression", "Understanding anxiety in pets") == "behavior"


def test_categorize_general():
    assert categorize_article("Adopting a Pet", "Things to consider before getting a new companion") == "general"


# ─────────────────────────────────────────────────────────────────────────────
# Tests for generate_summary
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_summary_short_text():
    text = "This is a short sentence."
    assert generate_summary(text) == text


def test_generate_summary_respects_max_chars():
    text = "First sentence. " * 30  # Long text
    result = generate_summary(text, max_chars=300)
    assert len(result) <= 300


def test_generate_summary_ends_at_sentence():
    text = "First sentence. Second sentence. " + "x" * 300
    result = generate_summary(text, max_chars=50)
    # Should end at "First sentence." or "Second sentence."
    assert result.endswith(".")


def test_generate_summary_word_boundary_fallback():
    # No sentence-ending punctuation within limit
    text = "word " * 100
    result = generate_summary(text, max_chars=30)
    assert len(result) <= 30
    # Should not end mid-word
    assert not result.endswith(" ")


def test_generate_summary_empty():
    assert generate_summary("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Tests for generate_article_id
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_article_id_length():
    result = generate_article_id("https://example.com/article")
    assert len(result) == 12


def test_generate_article_id_hex():
    result = generate_article_id("https://example.com/article")
    # Should be valid hex characters
    assert all(c in "0123456789abcdef" for c in result)


def test_generate_article_id_deterministic():
    url = "https://www.aspca.org/pet-care/dog-care/feeding"
    id1 = generate_article_id(url)
    id2 = generate_article_id(url)
    assert id1 == id2


def test_generate_article_id_unique_for_different_urls():
    id1 = generate_article_id("https://example.com/article-1")
    id2 = generate_article_id("https://example.com/article-2")
    assert id1 != id2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
