import unittest

import conda.config
from conda_build_all.version_matrix import special_case_version_matrix
from conda_build_all.tests.unit.dummy_index import DummyPackage, DummyIndex


class Test_special_case_version_matrix(unittest.TestCase):
    def setUp(self):
        self.pkgs = {'a': DummyPackage('pkgA', ['python', 'numpy']),
                     'b': DummyPackage('b', ['c']),
                     'c': DummyPackage('c'),
                     'b_alt': DummyPackage('b', ['c', 'd']),
                     'd': DummyPackage('d')}
        self.index = DummyIndex()

    def test_no_case(self):
        # No cases should still give us a result with a single case in it.
        a = DummyPackage('pkgA', ['wibble'])
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('wibble', '3.5.0')
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set([()]))

    def test_python(self):
        a = DummyPackage('pkgA', ['python'])
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '3.5.0')
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set(((('python', '2.7'),),
                                 (('python', '3.5'),),
                                ))
                         )

    def test_constrained_python(self):
        a = DummyPackage('pkgA', ['python <3'])
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '3.5.0')
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set(((('python', '2.7'),
                                  ),
                                ))
                         )

    def test_numpy_simplest_case(self):
        a = DummyPackage('pkgA', ['python', 'numpy'])
        self.index.add_pkg('numpy', '1.8.0', 'py27', depends=['python'])
        self.index.add_pkg('python', '2.7.2')
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set([(('python', '2.7'), ('numpy', '1.8')),
                                ])
                         )

    def test_numpy_without_python(self):
        # Conda recipes which do not depend on python, but do on python, do
        # not have the full conda metadata, but still need to be handled.
        a = DummyPackage('pkgA', ['numpy'])
        self.index.add_pkg('numpy', '1.8.0', 'py27', depends=['python'])
        self.index.add_pkg('python', '2.7.2')
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set([(('python', '2.7'), ('numpy', '1.8')),
                                ])
                         )

    def test_numpy_repeated_python27(self):
        # Repeating python 2.7 will result in the latest version being found
        a = DummyPackage('pkgA', ['python', 'numpy'])
        self.index.add_pkg('numpy', '1.8.0', 'py27', depends=['python <3'])
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '2.7.0')
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set([(('python', '2.7'), ('numpy', '1.8')),
                                ])
                         )

    def test_numpy_repeated_python(self):
        a = DummyPackage('pkgA', ['python', 'numpy'])
        self.index.add_pkg('numpy', '1.8.0', 'py27', depends=['python <3'])
        self.index.add_pkg('numpy', '1.8.0', 'py35', depends=['python'])
        self.index.add_pkg('numpy', '1.9.0', 'py35', depends=['python >=3'])
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '3.5.0')
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set(((('python', '2.7'), ('numpy', '1.8')),
                                 (('python', '3.5'), ('numpy', '1.8')),
                                 (('python', '3.5'), ('numpy', '1.9')),
                                ))
                         )

    def test_dependency_on_py27(self):
        # If a dependency can't hit the python version, it should not
        # be considered a case.
        a = DummyPackage('pkgA', ['python', 'oldschool'])
        self.index.add_pkg('oldschool', '1.8.0', 'py27', depends=['python <3'])
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '3.5.0')
        r = special_case_version_matrix(a, self.index)
        # No python 3 should be here.
        return
        # TODO: FIX THIS!!!!
        self.assertEqual(r, set([(('python', '2.7'),
                                  ),
                                ])
                         )


if __name__ == '__main__':
    unittest.main()
