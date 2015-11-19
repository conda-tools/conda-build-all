import os
import shutil
import tempfile
import unittest

import conda_build.config
from conda_build.metadata import MetaData

from conda_build_all.resolved_distribution import ResolvedDistribution
from conda_build_all.tests.unit.dummy_index import DummyIndex, DummyPackage


class Test_BakedDistribution(unittest.TestCase):
    # Tests cases where a recipe changes based on external
    # conditions, such as the definition of the PYTHON version.
    def setUp(self):
        self.recipe_dir = tempfile.mkdtemp(prefix='tmp_obvci_recipe_')

    def tearDown(self):
        shutil.rmtree(self.recipe_dir)

    def test_py_version_selector(self):
        recipe = """
            package:
                name: recipe_which_depends_on_py_version
                version: 3  # [py3k]
                version: 2  # [not py3k]
            """.replace('\n' + ' ' * 12, '\n').strip()
        with open(os.path.join(self.recipe_dir, 'meta.yaml'), 'w') as fh:
            fh.write(recipe)
        conda_build.config.config.CONDA_PY = 27
        meta = MetaData(self.recipe_dir)
        dist1 = ResolvedDistribution(meta, (('python', '27', ), ))
        self.assertEqual(dist1.version(), u'2')

        dist2 = ResolvedDistribution(meta, (('python', '35', ), ))
        self.assertEqual(dist2.version(), u'3')
        self.assertEqual(dist1.version(), u'2')

    def test_py_version_selector_skip(self):
        recipe = """
            package:
                name: recipe_which_depends_on_py_version
            build:  # [py35]
                skip: True  # [py3k]
            """.replace('\n' + ' ' * 12, '\n').strip()
        with open(os.path.join(self.recipe_dir, 'meta.yaml'), 'w') as fh:
            fh.write(recipe)
        conda_build.config.config.CONDA_PY = 27
        meta = MetaData(self.recipe_dir)
        dist1 = ResolvedDistribution(meta, (('python', '35', ), ))
        dist2 = ResolvedDistribution(meta, (('python', '34', ), ))

        self.assertEqual(dist1.skip(), True)
        self.assertEqual(dist2.skip(), False)


class Test_BakedDistribution_compute_matrix(unittest.TestCase):
    def setUp(self):
        self.index = DummyIndex()
        self.recipe_dir = tempfile.mkdtemp(prefix='tmp_obvci_recipe_')

    def tearDown(self):
        shutil.rmtree(self.recipe_dir)

    def test_py_xx_version(self):
        recipe = """
            package:
                name: recipe_which_depends_on_py_version
                version: 2
            requirements:
                build:
                 - python >=2.7
                 - numpy
                run:
                 - python x.x
                 - numpy x.x
            """
        with open(os.path.join(self.recipe_dir, 'meta.yaml'), 'w') as fh:
            fh.write(recipe)
        conda_build.config.config.CONDA_PY = 35
        conda_build.config.config.CONDA_NPY = 17

        meta = MetaData(self.recipe_dir)

        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '2.6.2')
        self.index.add_pkg('python', '3.5.0')
        self.index.add_pkg('numpy', '1.8.0', depends=['python'])
        r = ResolvedDistribution.compute_matrix(meta, self.index)
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0].build_id(), 'np18py27_0')
        self.assertEqual(r[1].build_id(), 'np18py35_0')

    def test_py_xx_version(self):
        recipe = """
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
            """
        with open(os.path.join(self.recipe_dir, 'meta.yaml'), 'w') as fh:
            fh.write(recipe)
        conda_build.config.config.CONDA_PY = 35

        meta = MetaData(self.recipe_dir)

        self.index.add_pkg('python', '2.7.2')
        self.index.add_pkg('python', '2.6.2')
        self.index.add_pkg('python', '3.5.0')
        resolved = ResolvedDistribution.compute_matrix(meta, self.index)
        ids = sorted(dist.build_id() for dist in resolved)
        self.assertEqual(ids, ['py26_0', 'py27_0'])


if __name__ == '__main__':
    unittest.main()
