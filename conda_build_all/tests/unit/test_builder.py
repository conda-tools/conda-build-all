import os
import shutil
import tempfile
import unittest
import textwrap

import conda_build.config
from conda_build.metadata import MetaData

from conda_build_all.builder import list_metas
from conda_build_all.tests.integration.test_builder import RecipeCreatingUnit


class Test_list_metas(RecipeCreatingUnit):
    def setUp(self):
        super(Test_list_metas, self).setUp()
        m1 = self.write_meta('m1', """
            package:
                name: m1
            """)
        m2 = self.write_meta('.', """
            package:
                name: m2
            """)
        m3 = self.write_meta('d1/d2/d3/meta3', """
            package:
                name: m3
            """)
        m4 = self.write_meta('da1/da2/da3/meta4', """
            package:
                name: m4
            """)

    def test_depth_0(self):
        metas = list_metas(self.recipes_root_dir, max_depth=0)
        names = [meta.name() for meta in metas]
        self.assertEqual(sorted(names), ['m1', 'm2', 'm3', 'm4'])

    def test_depth_m1(self):
        metas = list_metas(self.recipes_root_dir, max_depth=-1)
        names = [meta.name() for meta in metas]
        self.assertEqual(sorted(names), ['m1', 'm2', 'm3', 'm4'])

    def test_depth_1(self):
        metas = list_metas(self.recipes_root_dir, max_depth=1)
        names = [meta.name() for meta in metas]
        self.assertEqual(sorted(names), ['m2'])

    def test_depth_2(self):
        metas = list_metas(self.recipes_root_dir, max_depth=2)
        names = [meta.name() for meta in metas]
        self.assertEqual(sorted(names), ['m1', 'm2'])

    def test_default_depth(self):
        metas = list_metas(self.recipes_root_dir)
        names = [meta.name() for meta in metas]
        self.assertEqual(sorted(names), ['m1', 'm2', 'm3', 'm4'])

    def test_follow_symlink(self):
        link_dir = self.tmp_dir(prefix='recipes_through_links')
        os.symlink(os.path.join(self.recipes_root_dir, 'd1'),
                os.path.join(link_dir, 'd1'))
        os.symlink(os.path.join(self.recipes_root_dir, 'm1'),
                os.path.join(link_dir, 'm1'))
        metas = list_metas(link_dir)
        names = [meta.name() for meta in metas]
        self.assertEqual(sorted(names), ['m1', 'm3'])


class Test_sort_dependency_order(RecipeCreatingUnit):
    def setUp(self):
        super(Test_sort_dependency_order, self).setUp()
        a = self.write_meta('a', """
            package:
                name: a
            requirements:
                build:
                    - c
            """)

        b = self.write_meta('b', """
            package:
                name: b
            requirements:
                run:
                    - a  # [False]
            """)
        c = self.write_meta('c', """
            package:
                name: c
            """)

    def test_order_dependent_selector(self):
        # If we listen to the selectors, we would get a different build order.
        # As a result of https://github.com/SciTools/conda-build-all/issues/30
        # we know that we either have to resolve all dependencies up-front,
        # or simply ignore all selectors when dealing with sort order (but
        # emphatically not when building!).

        metas = list_metas(self.recipes_root_dir)
        from conda_build_all.builder import sort_dependency_order
        names = [m.name() for m in sort_dependency_order(metas)]
        self.assertEqual(names, ['c', 'a', 'b'])

 
if __name__ == '__main__':
    unittest.main()
