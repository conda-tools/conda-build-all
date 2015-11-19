import os
import shutil
import tempfile
import unittest
import textwrap

import conda_build.config
from conda_build.metadata import MetaData

from conda_build_all.resolved_distribution import ResolvedDistribution
from conda_build_all.tests.unit import RecipeCreatingUnit
from conda_build_all.tests.unit.dummy_index import DummyIndex, DummyPackage


class Test_BakedDistribution(RecipeCreatingUnit):
    # Tests cases where a recipe changes based on external
    # conditions, such as the definition of the PYTHON version.
    def test_py_version_selector(self):
        meta = self.write_meta("""
            package:
                name: recipe_which_depends_on_py_version
                version: 3  # [py3k]
                version: 2  # [not py3k]
            """)
        dist1 = ResolvedDistribution(meta, (('python', '27', ), ))
        dist2 = ResolvedDistribution(meta, (('python', '35', ), ))

        self.assertEqual(dist1.version(), u'2')
        self.assertEqual(dist2.version(), u'3')

    def test_py_version_selector_skip(self):
        meta = self.write_meta("""
            package:
                name: recipe_which_depends_on_py_version
            build:  # [py35]
                skip: True  # [py3k]
            """)
        dist1 = ResolvedDistribution(meta, (('python', '35', ), ))
        dist2 = ResolvedDistribution(meta, (('python', '34', ), ))

        self.assertEqual(dist1.skip(), True)
        self.assertEqual(dist2.skip(), False)


class Test_BakedDistribution_resolve_all(RecipeCreatingUnit):
    def test_py_xx_version(self):
        meta = self.write_meta("""
            package:
                name: recipe_which_depends_on_py_version
                version: 2
            requirements:
                build:
                 - python >=2.7
                 - numpy x.x
                run:
                 - python x.x
                 - numpy x.x
            """)
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '2.6.2')
        self.index.add_pkg('python', '3.5.0')
        self.index.add_pkg('numpy', '1.8.0', depends=['python'])
        resolved = ResolvedDistribution.resolve_all(meta, self.index)
        ids = sorted(dist.build_id() for dist in resolved)
        self.assertEqual(ids, ['np18py27_0', 'np18py35_0'])

    def test_skip_build(self):
        meta = self.write_meta("""
            package:
                name: recipe_which_depends_on_py_version
                version: 2
            build: # [py3k]
                skip: True  # [py3k]
            requirements:
                build:
                    - python
                run:
                    - python
            """)
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '2.6.2')
        self.index.add_pkg('python', '3.5.0')
        resolved = ResolvedDistribution.resolve_all(meta, self.index)
        ids = sorted(dist.build_id() for dist in resolved)
        self.assertEqual(ids, ['py26_0', 'py27_0'])

    def test_extra_conditions(self):
        meta = self.write_meta("""
                package:
                    name: test_recipe
                requirements:
                    build:
                        - python
                    run:
                        - python
                """)
        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '2.6.2')
        self.index.add_pkg('python', '3.5.0')
        resolved = ResolvedDistribution.resolve_all(meta, self.index,
                                       extra_conditions=['python 2.6.*|>=3'])
        ids = sorted(dist.build_id() for dist in resolved)
        self.assertEqual(ids, ['py26_0', 'py35_0'])


if __name__ == '__main__':
    unittest.main()
