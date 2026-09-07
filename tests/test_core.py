"""Regression tests for selected real deterministic utilities."""

from __future__ import annotations

import unittest

from aitran.contracts import TextDocument, TranslatedParagraph, parse_tagged_translation
from aitran.speech_chunking import chunk_speech_text, split_speech_chapters
from aitran.speech_pronunciation import Pronunciation, apply_pronunciations


class CoreTests(unittest.TestCase):
    def test_text_contract_round_trip_preserves_ids_and_spacing(self):
        source = "## Chapter 1\n\nFirst block.\n\nSecond block.\n"
        document = TextDocument.from_text(source)
        batch = document.slice(start=0, end=len(source))
        translated = tuple(
            TranslatedParagraph(item.paragraph_id, f"Перевод {index}")
            for index, item in enumerate(document.paragraphs, 1)
        )
        tagged = batch.render_tagged_translation(translated)
        parsed, errors = parse_tagged_translation(tagged, expected_ids=batch.paragraph_ids)
        self.assertEqual(errors, [])
        self.assertEqual(parsed, translated)
        self.assertEqual(batch.render_translation(parsed).count("\n\n"), 2)

    def test_speech_chunks_are_lossless_and_bounded(self):
        text = "## Глава 1\n\n" + ("Короткое предложение. " * 20) + "\n## Глава 2\n\nФинал.\n"
        chunks = chunk_speech_text(text, target_characters=90, max_characters=120)
        self.assertEqual("".join(item.text for item in chunks), text)
        self.assertTrue(all(len(item.text) <= 120 for item in chunks))
        self.assertEqual(len(split_speech_chapters(text)), 2)

    def test_pronunciation_changes_only_accent_positions(self):
        text = "Мира позвала Томаса, но Мира уже ушла."
        entries = (Pronunciation("Мира", "М+ира"),)
        result, count = apply_pronunciations(text, entries)
        self.assertEqual(count, 2)
        self.assertEqual(result.replace("+", ""), text)


if __name__ == "__main__":
    unittest.main()
