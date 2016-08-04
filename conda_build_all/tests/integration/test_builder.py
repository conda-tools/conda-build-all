from contextlib import contextmanager
import os
import shutil
import tempfile
import textwrap
import unittest

from conda_build.metadata import MetaData

from conda_build_all.resolved_distribution import ResolvedDistribution
from conda_build_all.builder import Builder
from conda_build_all.tests.unit.dummy_index import DummyIndex


sample_recipes = os.path.join(os.path.dirname(__file__), 'test_recipes')


class RecipeCreatingUnit(unittest.TestCase):
    def setUp(self):
        self.index = DummyIndex()
        self.directories_to_remove = []
        self.recipes_root_dir = self.tmp_dir(prefix='recipes')

    def tearDown(self):
        for directory in self.directories_to_remove:
            shutil.rmtree(directory)

    def tmp_dir(self, **mkdtemp_kwargs):
        tmp_dir = tempfile.mkdtemp(**mkdtemp_kwargs)
        self.directories_to_remove.append(tmp_dir)
        return tmp_dir

    def write_meta(self, recipe_dir_name, spec):
        recipe_dir = os.path.join(self.recipes_root_dir, recipe_dir_name)
        if not os.path.exists(recipe_dir):
            os.makedirs(recipe_dir)
        with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
            fh.write(textwrap.dedent(spec))
        return MetaData(recipe_dir)


class Test_build(RecipeCreatingUnit):
    def test_no_source(self):
        pkg1 = self.write_meta('pkg1', """
                    package:
                        name: pkg1
                        version: 1.0
                    """)
        pkg1_resolved = ResolvedDistribution(pkg1, (()))
        builder = Builder(None, None, None, None, None)
        r = builder.build(pkg1_resolved)
        self.assertTrue(os.path.exists(r))
        self.assertEqual(os.path.abspath(r), r)
        self.assertEqual(os.path.basename(r), 'pkg1-1.0-0.tar.bz2')


class Test__find_existing_built_dists(RecipeCreatingUnit):
    def make_channel(self, all_metas):
        for meta in all_metas:
            self.index.add_pkg_meta(meta)
        channel_root = tempfile.mkdtemp(prefix='temporary_channel_')
        # Line the directory up for removal when we're done with it.
        self.directories_to_remove.append(channel_root)
        
        self.index.write_to_channel(channel_root)
        return channel_root

    def setUp(self):
        super(Test__find_existing_built_dists, self).setUp()
        self.metas = {'a1': self.write_meta('a vn1', """
                    package:
                        name: a
                        version: 1.0
                    """),
                      'a2': self.write_meta('a vn2', """
                    package:
                        name: a
                        version: 2.0
                    """),
                      'a2_1': self.write_meta('a vn2 bld1', """
                    package:
                        name: a
                        version: 2.0
                    build:
                        number: 1
                    """),
                      'b2': self.write_meta('b vn2', """
                    package:
                        name: b
                        version: 2.0
                    requirements:
                        run:
                            - a 2.*
                    """)}

    def test_exist_on_channel(self):
        channel = self.make_channel(self.metas.values())
        channel_url = 'file://' + channel
        builder = Builder('.', [channel_url], [], [], [])
        expected_channel = '{}/{}'.format(channel_url, self.metas['a1'].info_index()['subdir'])
        existing = builder.find_existing_built_dists([self.metas['a1'], self.metas['a2']])
        dists = [(meta.dist(), locn) for meta, locn in existing]
        self.assertEqual(dists, [('a-1.0-0', expected_channel),
                                 ('a-2.0-0', expected_channel)])

    def test_full_version_exists_on_channel(self):
        # Only a vn2.0 build 1 is available, we want to assert that nothing is found for a1 and a2 build 0.
        channel = self.make_channel([self.metas['a2_1']])
        builder = Builder('.', ['file://' + channel], [], [], [])
        existing = builder.find_existing_built_dists([self.metas['a1'], self.metas['a2']])
        self.assertEqual([(meta.dist(), locn) for meta, locn in existing],
                         [('a-1.0-0', None), ('a-2.0-0', None)])


    def test_exists_in_directory(self):
        distribution_directory = tempfile.mkdtemp()
        # Line the directory up for removal when we're done with it.
        self.directories_to_remove.append(distribution_directory)

        with open(os.path.join(distribution_directory, self.metas['a1'].dist() + '.tar.bz2'), 'w') as fh:
            fh.write('placeholder')
        builder = Builder('.', [], [distribution_directory], [], [])
        existing = builder.find_existing_built_dists([self.metas['a1'], self.metas['a2']])
        dists = [(meta.dist(), locn) for meta, locn in existing]
        self.assertEqual(dists, [('a-1.0-0', distribution_directory), ('a-2.0-0', None)])


class Test_compute_build_distros(RecipeCreatingUnit):
    def test_added_to_index(self):
        metas = [self.write_meta('py2k', """
                    package:
                        name: python
                        version: 2.7.0
                    """),
                 self.write_meta('py33', """
                    package:
                        name: python
                        version: 3.3.0
                    """),
                 self.write_meta('py34', """
                    package:
                        name: python
                        version: 3.4.24
                    """),
                 self.write_meta('py35', """
                    package:
                        name: python
                        version: 3.5.2
                    build:
                        number: 1
                    """),
                 self.write_meta('np110', """
                    package:
                        name: numpy
                        version: 1.10
                    requirements:
                        build:
                            - python
                        run:
                            - python
                    """),
                self.write_meta('py_package', """
                    package:
                        name: my_py_package
                        version: 2.0
                    requirements:
                        build:
                            - python
                        run:
                            - python
                            - numpy
                    """)]
        builder = Builder(None, None, None, None, None)
        index = {}
        distributions = builder.compute_build_distros(index, metas)
        expected = ['python-2.7.0-0', 'python-3.3.0-0', 'python-3.4.24-0',
                    'python-3.5.2-1',
                    'numpy-1.10-py27_0', 'numpy-1.10-py34_0', 'numpy-1.10-py35_0',
                    'my_py_package-2.0-py27_0', 'my_py_package-2.0-py34_0',
                    'my_py_package-2.0-py35_0']
        self.assertEqual([meta.dist() for meta in distributions], expected)
        # Check that we didn't change the index.
        self.assertEqual(index, {}) 


if __name__ == '__main__':
    unittest.main()
