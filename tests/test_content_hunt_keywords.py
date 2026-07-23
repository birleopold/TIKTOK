from __future__ import annotations

import unittest

from unified_app.services.content_hunt import (
    _decode_search_url,
    _platform_query,
    classify_url,
    looks_like_url,
)


class KeywordHuntTests(unittest.TestCase):
    def test_keywords_are_not_treated_as_urls(self):
        self.assertFalse(looks_like_url("best student laptops Uganda"))

    def test_public_urls_are_detected(self):
        self.assertTrue(looks_like_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(looks_like_url("www.tiktok.com/@creator"))

    def test_platform_query_uses_site_filters(self):
        self.assertIn("site:youtube.com", _platform_query("laptop tips", "youtube"))
        self.assertIn("site:tiktok.com", _platform_query("laptop tips", "tiktok"))

    def test_duckduckgo_redirect_is_unwrapped(self):
        wrapped = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle"
        self.assertEqual(_decode_search_url(wrapped), "https://example.com/article")

    def test_platform_classification_uses_real_hosts(self):
        self.assertEqual(classify_url("https://www.tiktok.com/@creator"), "tiktok")
        self.assertEqual(classify_url("https://youtube.com/watch?v=x"), "youtube")
        self.assertEqual(classify_url("https://tiktok.com.example.org/video"), "web")


if __name__ == "__main__":
    unittest.main()
