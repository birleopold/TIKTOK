from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from unified_app.services.hunt_downloads import (
    HuntDownloadCandidate,
    _duration_text,
    _metadata_path,
    slugify,
)


class HuntDownloadTests(unittest.TestCase):
    def test_slugify_creates_safe_folder_name(self):
        self.assertEqual(slugify("Dell Latitude 7400 / Review"), "dell-latitude-7400-review")

    def test_slugify_uses_fallback(self):
        self.assertEqual(slugify("***", fallback="saved"), "saved")

    def test_duration_text(self):
        self.assertEqual(_duration_text(125), "2:05")
        self.assertEqual(_duration_text(3723), "1:02:03")
        self.assertEqual(_duration_text(None), "unknown")

    def test_metadata_path_keeps_video_extension_visible(self):
        path = Path("clip.mp4")
        self.assertEqual(_metadata_path(path), Path("clip.mp4.source.json"))

    def test_candidate_dataclass_preserves_selection_data(self):
        row = HuntDownloadCandidate(
            7,
            "youtube",
            "Test video",
            "https://example.com/video",
            "Description",
            "candidate",
            "2026-07-23T00:00:00+00:00",
        )
        self.assertEqual(row.id, 7)
        self.assertEqual(row.source_type, "youtube")


if __name__ == "__main__":
    unittest.main()
