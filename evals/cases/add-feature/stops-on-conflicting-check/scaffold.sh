#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
ci_state green
printf 'import unittest\n\nfrom tally import core\n\n\nclass TestLegacy(unittest.TestCase):\n    @unittest.skipUnless(hasattr(core, "median"), "no median yet")\n    def test_median_of_four_is_the_lower_middle(self):\n        self.assertEqual(core.median([1, 2, 3, 4]), 2)\n' > tests/test_legacy.py
git add tests/test_legacy.py
git commit -q -m 'Add a legacy median test'
git push -q origin main
ci_state green
