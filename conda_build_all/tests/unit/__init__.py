import os
import tempfile
import textwrap
import shutil
import unittest

from conda_build.metadata import MetaData

from conda_build_all.tests.unit.dummy_index import DummyIndex


class RecipeCreatingUnit(unittest.TestCase):
    def setUp(self):
        self.index = DummyIndex()
        self.recipe_dir = tempfile.mkdtemp(prefix='tmp_recipe_')

    def tearDown(self):
        shutil.rmtree(self.recipe_dir)

    def write_meta(self, spec):
        with open(os.path.join(self.recipe_dir, 'meta.yaml'), 'w') as fh:
            fh.write(textwrap.dedent(spec))
        return MetaData(os.path.join(self.recipe_dir))
