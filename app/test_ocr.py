import unittest
from unittest.mock import Mock, patch

from app.ocr import _parse_tsv, extract_pdf_page


class ParseTesseractTsvTests(unittest.TestCase):
    def test_groups_words_by_line_and_normalizes_confidence(self):
        tsv = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "4\t1\t1\t1\t1\t0\t0\t0\t10\t10\t-1\t\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t5\t5\t80\tHola\n"
            "5\t1\t1\t1\t1\t2\t6\t0\t5\t5\t100\tmundo\n"
            "5\t1\t1\t1\t2\t1\t0\t8\t5\t5\t60\tAdios\n"
        )

        self.assertEqual(_parse_tsv(tsv), (["Hola mundo", "Adios"], [0.9, 0.6]))


class ExtractPdfPageTests(unittest.TestCase):
    def test_prefers_text_layer_and_closes_rendered_image_after_ocr(self):
        page = Mock()
        with patch("app.ocr.page_text_layer", return_value="embedded text"), patch(
            "app.ocr.ocr_page"
        ) as ocr_page:
            self.assertEqual(extract_pdf_page(page), (["embedded text"], [1.0], True))
            page.render.assert_not_called()
            ocr_page.assert_not_called()

        image = Mock()
        page.render.return_value.to_pil.return_value = image
        with patch("app.ocr.page_text_layer", return_value=None), patch(
            "app.ocr.ocr_page", return_value=(["scanned text"], [0.8])
        ):
            self.assertEqual(extract_pdf_page(page), (["scanned text"], [0.8], False))
        image.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
