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

   
if __name__ == '__main__':
    unittest.main()
