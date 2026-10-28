import io
import unittest
from contextlib import redirect_stdout

from tally import cli


class TestCli(unittest.TestCase):
    def test_prints_total_and_average(self):
        out = io.StringIO()
        with redirect_stdout(out):
            cli.main(["2", "4"])
        self.assertEqual(out.getvalue().strip(), "total=6.0 average=3.0")


if __name__ == "__main__":
    unittest.main()
