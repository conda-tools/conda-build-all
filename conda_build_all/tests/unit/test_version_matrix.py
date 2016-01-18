import unittest

import conda.config
from conda_build_all.version_matrix import (special_case_version_matrix,
                                            filter_cases,
                                            keep_top_n_major_versions,
                                            keep_top_n_minor_versions)
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

    def test_python_itself(self):
        a = DummyPackage('python', version="abc")
        r = special_case_version_matrix(a, self.index)
        self.assertEqual(r, set(((('python', 'abc'),),
                                ))
                         )

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
        # TODO: Enable this test.
        return
        # No python 3 should be here.
    #    self.assertEqual(r, set([(('python', '2.7'),
    #                                  ),
    #                            ])
    #                     )

    def test_numpy_xx(self):
        """
        Check whether the numpy x.x version spec generates the right cases.
        """

        # Build an index that contains numpy 1.9 and 1.10 on python 2.7 and
        # 3.5 for a total of 4 numpy/python combinations.
        pythons = ['2.7', '3.5']
        # Only major/minor in the numpy list here because that is what is used
        # for the build matrix.
        numpys = ['1.9', '1.10']
        for python_version in pythons:
            python_build_string = 'py' + python_version.replace('.', '')
            self.index.add_pkg('python', python_version)
            for numpy_version in numpys:
                # Add a patch version to each numpy since that is how the
                # versions are numbered.
                self.index.add_pkg('numpy',
                                   numpy_version + '.2',
                                   python_build_string,
                                   depends=['python ' + python_version])

        # Cases to check
        numpy_dep_cases = []
        expect_result = []

        # Case 1:
        #   Only a numpy x.x spec, expect all four cases to be in the matrix.

        # Add case.
        numpy_dep_cases.append(('numpy x.x', 'python'))
        # Generate expected results for this case.
        results = []
        for python in pythons:
            for numpy in numpys:
                results.append((('python', python), ('numpy', numpy)))

        expect_result.append(results)

        # Case 2:
        #   A numpy x.x spec and a numpy version restriction which does NOT
        #   exclude any of the cases in the DummyIndex. Again, expect all
        #   four cases to be in the result.

        # Add case.
        numpy_dep_cases.append(('numpy x.x', 'numpy >1.6', 'python'))

        # Generate expected results for this case.
        results = []
        for python in pythons:
            for numpy in numpys:
                results.append((('python', python), ('numpy', numpy)))
        expect_result.append(results)

        # Case 3:
        #   A numpy x.x spec and a numpy version restriction which does
        #   eliminate one the numpy versions in the DummyIndex. Expect only
        #   the numpy 1.9 case to survive.

        # Add case 3.
        numpy_dep_cases.append(('numpy x.x', 'numpy >=1.10', 'python'))

        # Generate expected results for case 3.
        results = []
        for python in pythons:
            for numpy in numpys[1:]:
                results.append((('python', python), ('numpy', numpy)))
        expect_result.append(results)

        for dep, result in zip(numpy_dep_cases, expect_result):
            print(dep)
            a = DummyPackage('pkgA', dep, dep)

            r = special_case_version_matrix(a, self.index)
            self.assertEqual(set(r), set(result),
                             msg='got: {}\nexpected: {}'.format(r, result))


class CasesTestCase(unittest.TestCase):
    def setUp(self):
        self.item = {
                     'py26': ('python', '2.6'),
                     'py27': ('python', '2.7'),
                     'py34': ('python', '3.4'),
                     'py35': ('python', '3.5'),
                     'o12': ('other', '1.2'),
                     'o13': ('other', '1.3'),
                     'np19': ('numpy', '1.9'),
                     'np110': ('numpy', '1.10'),
                     'np21': ('numpy', '2.1'),
                     }


class Test_filter_cases(CasesTestCase):
    # n.b. We should be careful not to test MatchSpec functionality here.

    def test_nothing(self):
        self.assertEqual(list(filter_cases([], [])), [])

    def test_no_filter(self):
        cases = ([self.item['py26']],
                 [self.item['py35']])
        self.assertEqual(tuple(filter_cases(cases, [])), cases)

    def test_single_filter(self):
        cases = ([self.item['py26']],
                 [self.item['py35']])
        self.assertEqual(tuple(filter_cases(cases, ['python >=3'])), cases[1:])

    def test_multiple_filter(self):
        cases = ([self.item['py26']],
                 [self.item['py34']],
                 [self.item['py35']])
        self.assertEqual(tuple(filter_cases(cases, ['python >=3', 'python <=3.4'])), cases[1:2])

    def test_multiple_filter(self):
        cases = ([self.item['py26'], self.item['np110']],
                 [self.item['py34'], self.item['np19']],
                 [self.item['py35'], self.item['np110']])
        self.assertEqual(tuple(filter_cases(cases, ['python >=3', 'numpy 1.10.*'])), cases[2:])

    def test_other_cases(self):
        cases = ([self.item['py26'], self.item['o12']],
                 [self.item['py34'], self.item['o12']],
                 [self.item['py35'], self.item['o13']])
        self.assertEqual(tuple(filter_cases(cases, ['other 1.2.*'])), cases[:2])


class Test_keep_top_n_major_versions(CasesTestCase):
    def test_keep_less_than_n(self):
        cases = ([self.item['py26']],)
        self.assertEqual(tuple(keep_top_n_major_versions(cases, 2)),
                         cases)

    def test_keep_1(self):
        cases = ([self.item['py27']],
                 [self.item['py35']])
        self.assertEqual(tuple(keep_top_n_major_versions(cases, 1)),
                         cases[1:])

    def test_keep_2(self):
        cases = ([self.item['py27']],
                 [self.item['py35']])
        self.assertEqual(tuple(keep_top_n_major_versions(cases, 2)),
                         cases)

    def test_keep_0(self):
        cases = ([self.item['py27']],
                 [self.item['py35']])
        self.assertEqual(tuple(keep_top_n_major_versions(cases, 0)),
                         cases)

    def test_multiple_packages(self):
        cases = ([self.item['py35'], self.item['np110']],
                 [self.item['py35'], self.item['np21']],
                 [self.item['py27'], self.item['np110']],
                 [self.item['py27'], self.item['np21']])
        self.assertEqual(tuple(keep_top_n_major_versions(cases, 1)),
                         cases[1:2])

    def test_multiple_packages_leaves_nothing(self):
        cases = ([self.item['py35'], self.item['np110']],
                 [self.item['py27'], self.item['np21']])
        self.assertEqual(tuple(keep_top_n_major_versions(cases, 1)),
                         ())


class Test_keep_top_n_minor_versions(CasesTestCase):
    def test_keep_less_than_n(self):
        cases = ([self.item['py26']],)
        self.assertEqual(tuple(keep_top_n_minor_versions(cases, 2)),
                         cases)

    def test_keep_1(self):
        cases = ([self.item['py26']],
                 [self.item['py27']],
                 [self.item['py34']],
                 [self.item['py35']])
        self.assertEqual(tuple(keep_top_n_minor_versions(cases, 1)),
                         cases[1::2])

    def test_keep_2(self):
        cases = ([self.item['py26']],
                 [self.item['py27']],
                 [self.item['py35']])
        self.assertEqual(tuple(keep_top_n_minor_versions(cases, 2)),
                         cases)

    def test_keep_0(self):
        cases = ([self.item['py26']],
                 [self.item['py35']])
        self.assertEqual(tuple(keep_top_n_minor_versions(cases, 0)),
                         cases)

    def test_multiple_packages(self):
        cases = ([self.item['py26'], self.item['np19']],
                 [self.item['py26'], self.item['np110']],
                 [self.item['py27'], self.item['np110']])
        self.assertEqual(tuple(keep_top_n_minor_versions(cases, 1)),
                         cases[2:])



#    def test_keep_0(self):



if __name__ == '__main__':
    unittest.main()
