from __future__ import annotations

import unittest

from unified_app.services.content_hunt import (
    _decode_search_url,
    _platform_query,
    _rank_search_results,
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

    def test_exact_model_result_outranks_generic_brand_pages(self):
        rows = [
            {
                "title": "Computers and Technology Solutions | Dell",
                "url": "https://www.dell.com/en-us",
                "description": "Shop Dell laptops, monitors and accessories.",
            },
            {
                "title": "Dell Latitude 7400 Review and Specifications",
                "url": "https://example.com/dell-latitude-7400-review",
                "description": "Full Dell Latitude 7400 specifications and review.",
            },
        ]
        ranked = _rank_search_results(rows, "dell latitude 7400", 10)
        self.assertEqual(len(ranked), 1)
        self.assertIn("latitude-7400", ranked[0]["url"])

    def test_wikipedia_is_suppressed_for_product_searches(self):
        rows = [
            {
                "title": "Dell Latitude 7400",
                "url": "https://en.wikipedia.org/wiki/Dell_Latitude",
                "description": "Dell Latitude 7400 computer model.",
            },
            {
                "title": "Dell Latitude 7400 Review",
                "url": "https://example.com/reviews/dell-latitude-7400",
                "description": "Dell Latitude 7400 review and specifications.",
            },
        ]
        ranked = _rank_search_results(rows, "dell latitude 7400", 10)
        self.assertEqual(ranked[0]["url"], "https://example.com/reviews/dell-latitude-7400")

    def test_two_word_search_requires_both_words(self):
        rows = [
            {
                "title": "Laptop deals",
                "url": "https://example.com/laptops",
                "description": "New laptops for sale.",
            },
            {
                "title": "Used laptop deals",
                "url": "https://shop.example.org/used-laptops",
                "description": "Affordable used laptop offers.",
            },
        ]
        ranked = _rank_search_results(rows, "used laptop", 10)
        self.assertEqual(len(ranked), 1)
        self.assertIn("used-laptops", ranked[0]["url"])


if __name__ == "__main__":
    unittest.main()
