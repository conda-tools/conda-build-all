import os
import shutil
import tempfile
import textwrap
import unittest

from conda_build.metadata import MetaData

from conda_build_all.builder import Builder
from conda_build_all.tests.unit.dummy_index import DummyIndex

sample_recipes = os.path.join(os.path.dirname(__file__), 'test_recipes')


class RecipeCreatingUnit(unittest.TestCase):
    def setUp(self):
        self.index = DummyIndex()
        self.recipes_root_dir = tempfile.mkdtemp(prefix='recipes')
        self.directories_to_remove = [self.recipes_root_dir]

    def tearDown(self):
        for directory in self.directories_to_remove:
            shutil.rmtree(directory)

    def write_meta(self, recipe_dir_name, spec):
        recipe_dir = os.path.join(self.recipes_root_dir, recipe_dir_name)
        os.mkdir(recipe_dir)
        with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
            fh.write(textwrap.dedent(spec))
        return MetaData(recipe_dir)


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
        expected_channel = '{}/{}/'.format(channel_url, self.metas['a1'].info_index()['subdir'])
        existing = builder.find_existing_built_dists([self.metas['a1'], self.metas['a2']])
        dists = [(meta.dist(), locn) for meta, locn in existing]
        self.assertEqual(dists, [('a-1.0-0', expected_channel),
                                 ('a-2.0-0', expected_channel)])

    def test_full_version_exists_on_channel(self):
        # Only a vn2.0 build 1 is available, we want to assert that nothing is found for a1 and a2 build 0.
        channel = self.make_channel([self.metas['a2_1']])
        print(channel)
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


if __name__ == '__main__':
    unittest.main()
