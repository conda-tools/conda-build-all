import os
import unittest

from binstar_client.utils import get_binstar
from argparse import Namespace
try:
    import conda_build.api
except ImportError:
    import conda_build.config

from conda_build_all.build import build, upload
from conda_build_all.inspect_binstar import (distribution_exists,
                                             distribution_exists_on_channel,
                                             add_distribution_to_channel,
                                             copy_distribution_to_owner)
from conda_build_all.tests.integration.test_builder import RecipeCreatingUnit



def clear_binstar(cli, owner):
    """
    Empty all distributions for a user.

    The "rm -rf *" of the binstar world.

    """
    for channel in cli.list_channels(owner):
        cli.remove_channel(owner, channel)

    for package in cli.user_packages(owner):
        cli.remove_package(owner, package['name'])


OWNER = 'Obvious-ci-tests'
CLIENT = get_binstar(Namespace(token=os.environ.get('BINSTAR_TOKEN', None), site=None))


@unittest.skipIf(os.environ.get('CONDA_BUILD_ALL_TEST_ANACONDA_CLOUD', False) != '1',
                 "Not testing real binstar usage as the "
                 "CONDA_BUILD_ALL_TEST_ANACONDA_CLOUD environment variable is not "
                 "set to '1'.")
class Test(RecipeCreatingUnit):
    # Note: These tests upload things to anaconda.org and are completely global. That is,
    # if somebody else in the world is running the tests at the same time anywhere on the planet,
    # they will behave in very strange ways (highly likely to fail).
    def setUp(self):
        clear_binstar(CLIENT, OWNER)
        super(Test, self).setUp()

    def tearDown(self):
        clear_binstar(CLIENT, OWNER)
        super(Test, self).tearDown()

    def test_distribution_exists(self):
        # Build a recipe.
        meta = self.write_meta('test_recipe_1', """
                    package:
                        name: test_recipe_1
                        version: 'determined_at_build_time'
                    build:
                        script: echo "v0.1.0.dev1" > __conda_version__.txt
                    """)
        meta = build(meta)
        if hasattr(conda_build, 'api'):
            build_config = conda_build.api.Config()
        else:
            build_config = conda_build.config.config

        # Check distribution exists returns false when there is no distribution.
        self.assertFalse(distribution_exists(CLIENT, OWNER, meta))

        # upload the distribution 
        upload(CLIENT, meta, OWNER, channels=['testing'], config=build_config)

        # Check the distribution exists. Notice there is no channel being supplied here.
        self.assertTrue(distribution_exists(CLIENT, OWNER, meta))

        # Check the distribution is on testing but not on main.
        self.assertTrue(distribution_exists_on_channel(CLIENT, OWNER, meta, channel='testing'))
        self.assertFalse(distribution_exists_on_channel(CLIENT, OWNER, meta, channel='main'))

        add_distribution_to_channel(CLIENT, OWNER, meta, channel='main')
        # Check that the distribution has been added.
        self.assertTrue(distribution_exists_on_channel(CLIENT, OWNER, meta, channel='main'))

        # Add the meta for a recipe known to exist on conda-forge
        meta2 = self.write_meta('conda_build_all', """
                                package:
                                    name: conda-build-all
                                    version: 0.12.0
                                """)
        copy_distribution_to_owner(CLIENT, 'conda-forge', OWNER, meta2, channel='main')
        self.assertTrue(distribution_exists_on_channel(CLIENT, OWNER, meta2))


if __name__ == '__main__':
    unittest.main()
