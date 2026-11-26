"""Checks that the my_evox package is installed and can be imported."""

import importlib
import unittest


class PackageTest(unittest.TestCase):
    def test_the_package_imports(self) -> None:
        """The package is installed: importing it works from anywhere."""
        package = importlib.import_module("my_evox")
        self.assertEqual(package.__name__, "my_evox")


if __name__ == "__main__":
    unittest.main()
