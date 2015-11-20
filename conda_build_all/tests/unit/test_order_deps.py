import unittest

from conda_build_all.order_deps import resolve_dependencies


class Test_resolve_dependencies(unittest.TestCase):
    def test_example(self):
        deps = resolve_dependencies({'a': ['b', 'c'], 'b': ['c'],
                                     'c': ['d'], 'd': []})
        self.assertEqual(list(deps), ['d', 'c', 'b', 'a'])

    def test_unresolvable(self):
        deps = resolve_dependencies({'a': 'b', 'b': 'a'})
        with self.assertRaises(ValueError):
            list(deps)

    def test_missing_link(self):
        deps = resolve_dependencies({'a': 'b', 'c': 'd'})
        with self.assertRaises(ValueError):
            list(deps)

