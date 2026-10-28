import unittest

from tally import core


class TestCore(unittest.TestCase):
    def test_total(self):
        self.assertEqual(core.total([1, 2, 3]), 6)

    def test_average(self):
        self.assertEqual(core.average([2, 4]), 3)

    def test_top(self):
        self.assertEqual(core.top([1, 5, 3], 2), [5, 3])


if __name__ == "__main__":
    unittest.main()
