# There should be *very* few tests here. The intention of this module is to test the
# conda-build-all interface for a few cases to ensure that when pulling all of the
# components together, we get the desired behaviour. Please consider adding *unit*
# tests for new functionality.

from argparse import Namespace
from contextlib import contextmanager
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from binstar_client.utils import get_binstar
import conda.config

from conda_build_all.build import build, upload
from conda_build_all.inspect_binstar import (distribution_exists,
                                             distribution_exists_on_channel,
                                             add_distribution_to_channel)
from conda_build_all.tests.integration.test_builder import RecipeCreatingUnit
from conda_build_all.resolved_distribution import ResolvedDistribution


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
        self.conda_bld_root = tempfile.mkdtemp(prefix='conda_bld_dir_')
        super(Test, self).setUp()

    def tearDown(self):
        clear_binstar(CLIENT, OWNER)
        shutil.rmtree(self.conda_bld_root)
        super(Test, self).tearDown()

    @contextmanager
    def configure_conda(self):
        condarc = os.path.join(self.conda_bld_root, 'condarc')
        with open(condarc, 'w') as fh:
            fh.write(textwrap.dedent("""
                channels: []
                add_pip_as_python_dependency: False
                conda-build:
                    root-dir: {}
                """.format(self.conda_bld_root)))
        yield condarc

    def call(self, cmd_args):
        cmd = [sys.executable, '-m', 'conda_build_all.cli'] + list(cmd_args)
        environ = os.environ.copy()
        # Use a very limited condarc config.
        with self.configure_conda() as rc_path:
            environ['CONDARC'] = rc_path
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 env=environ, bufsize=0)
            line = p.stdout.readline()
            while line:
                print(str(line.rstrip().decode('utf8')))
                line = p.stdout.readline()
            # Wait for the return code.
            p.communicate()
        self.assertEqual(p.returncode, 0, 'Exit code was not 0 (got {})'.format(p.returncode))

    def test(self):
        # Build a recipe.
        py2 = self.write_meta('py1', """
                    package:
                        name: python
                        version: 1.2.3
                    """)
        py2 = self.write_meta('py2', """
                    package:
                        name: python
                        version: 2.1.10
                    """)
        a = self.write_meta('a', """
                    package:
                        name: a
                        version: 3.1.4
                    requirements:
                        build:
                            - python
                        run:
                            - python
                    """)

        a_py12 = ResolvedDistribution(a, (('python', '12', ), ))
        a_py21 = ResolvedDistribution(a, (('python', '21', ), ))
        a_py99 = ResolvedDistribution(a, (('python', '99', ), ))

        testing_channel = '{}/channel/{}'.format(OWNER, 'testing')
        self.call([self.recipes_root_dir, '--upload-channel', testing_channel])

        # Check that we have started on the right footing - the distribution should be on testing,
        # but not on main.
        self.assertTrue(distribution_exists_on_channel(CLIENT, OWNER, py2, channel='testing'))
        self.assertFalse(distribution_exists_on_channel(CLIENT, OWNER, py2, channel='main'))

        # Check that we've had a py21 and py12, but not a py99 for a.
        self.assertTrue(distribution_exists_on_channel(CLIENT, OWNER, a_py12, channel='testing'))
        self.assertTrue(distribution_exists_on_channel(CLIENT, OWNER, a_py21, channel='testing'))
        self.assertFalse(distribution_exists_on_channel(CLIENT, OWNER, a_py99, channel='testing'))

        # Remove the built distribution, re-run, and assert that we didn't bother re-building.
        dist_path = os.path.join(self.conda_bld_root, conda.config.subdir, a_py21.pkg_fn())
        self.assertTrue(os.path.exists(dist_path))
        os.remove(dist_path)
        self.call([self.recipes_root_dir, '--inspect-channel', testing_channel, '--upload-channel', testing_channel])
        self.assertFalse(os.path.exists(dist_path))

        # Now put a condition in. In this case, only build dists for py<2
        CLIENT.remove_dist(OWNER, a_py21.name(), a_py21.version(), '{}/{}'.format(conda.config.subdir, a_py21.pkg_fn()))
        self.assertFalse(distribution_exists_on_channel(CLIENT, OWNER, a_py21, channel='testing'))
        self.call([self.recipes_root_dir, '--inspect-channel', testing_channel, '--upload-channel', testing_channel,
                   '--matrix-condition', 'python <2'])
        self.assertFalse(distribution_exists_on_channel(CLIENT, OWNER, a_py21, channel='testing'))
        self.assertFalse(os.path.exists(dist_path))

        # Without the condition, we should be re-building the distribution
        self.call([self.recipes_root_dir, '--inspect-channel', testing_channel, '--upload-channel', testing_channel])
        self.assertTrue(os.path.exists(dist_path))
        self.assertTrue(distribution_exists_on_channel(CLIENT, OWNER, a_py21, channel='testing'))


if __name__ == '__main__':
    unittest.main()
