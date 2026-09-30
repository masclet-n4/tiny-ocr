import unittest

from app.ocr import _parse_tsv


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


if __name__ == "__main__":
    unittest.main()
