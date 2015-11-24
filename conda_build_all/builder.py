"""
Build all the conda recipes in the given directory sequentially if they do not
already exist on the given binstar channel.
Building is done in order of dependencies (circular dependencies are not supported).
Once a build is complete, the distribution will be uploaded (provided BINSTAR_TOKEN is
defined), and the next package will be processed.

"""
from __future__ import print_function

import glob
import logging
import os
import subprocess
from argparse import Namespace

from binstar_client.utils import get_binstar
import binstar_client
from conda.api import get_index
from conda_build.metadata import MetaData
from conda_build.build import bldpkg_path
import conda.config

from . import order_deps
from . import build
from . import inspect_binstar
from . import version_matrix as vn_matrix
from . import resolved_distribution


def package_built_name(package, root_dir):
    package_dir = os.path.join(root_dir, package)
    meta = MetaData(package_dir)
    return bldpkg_path(meta)


def distribution_exists(binstar_cli, owner, metadata):
    fname = '{}/{}.tar.bz2'.format(conda.config.subdir, metadata.dist())
    try:
        r = binstar_cli.distribution(owner, metadata.name(), metadata.version(),
                                     fname)
        exists = True
    except binstar_client.errors.NotFound:
        exists = False
    return exists


def fetch_metas(directory):
    """
    Get the build metadata of all recipes in a directory.

    The recipes will be sorted by the order of their directory name.

    """
    packages = []
    for package_name in sorted(os.listdir(directory)):
        package_dir = os.path.join(directory, package_name)
        meta_yaml = os.path.join(package_dir, 'meta.yaml')

        if os.path.isdir(package_dir) and os.path.exists(meta_yaml):
            packages.append(MetaData(package_dir))

    return packages


def sort_dependency_order(metas):
    """Sort the metas into the order that they must be built."""
    meta_named_deps = {}
    buildable = [meta.name() for meta in metas]
    for meta in metas:
        all_deps = ((meta.get_value('requirements/run', []) or []) +
                    (meta.get_value('requirements/build', []) or []))
        # Remove version information from the name.
        all_deps = [dep.split(' ', 1)[0] for dep in all_deps]
        meta_named_deps[meta.name()] = [dep for dep in all_deps if dep in buildable]
    sorted_names = list(order_deps.resolve_dependencies(meta_named_deps))
    return sorted(metas, key=lambda meta: sorted_names.index(meta.name()))


class Builder(object):
    def __init__(self, conda_recipes_directory,
                 inspection_channels, inspection_directories,
                 artefact_destinations,
                 matrix_conditions, matrix_max_n_major_minor_versions=(2, 2)):
        """
        Build a directory of conda recipes sequentially, if they don't already exist in the inspection locations.
#        If the build does exist on the binstar account, but isn't in the targeted channel, it will be added to artefact_destinations,
        All newly-built distributions will be uploaded to artefact_destinations. If any destination is file:// based, it will be copied,
        if url:// it will be uploaded with anaconda-client.

        """
        self.conda_recipes_directory = conda_recipes_directory
        self.inspection_channels = inspection_channels
        self.inspection_directories = inspection_directories
        self.artefact_destinations = artefact_destinations or []
        self.matrix_conditions = matrix_conditions
        self.matrix_max_n_major_minor_versions = matrix_max_n_major_minor_versions

        self.upload_owner = 'pelson'
        self.upload_channel = 'dev'

        self.anaconda_cli = None
        # get_binstar(Namespace(token=self.binstar_token, site=None))

    def fetch_all_metas(self):
        """
        Return the conda recipe metas, in the order they should be built.

        """
        conda_recipes_directory = os.path.abspath(os.path.expanduser(self.conda_recipes_directory))
        recipe_metas = fetch_metas(conda_recipes_directory)
        recipe_metas = sort_dependency_order(recipe_metas)
        return recipe_metas

    def find_existing_built_dists(self, recipe_metas):
        recipes = tuple([meta, None] for meta in recipe_metas)
        if self.inspection_channels:
            # For an unknown reason we are unable to cache the get_index call. There is a
            # test which fails against v3.18.6 if use_cache is True.
            index = get_index(self.inspection_channels, prepend=False, use_cache=False)
            # We look to see if a distribution exists in the channel. Note: This is not checking
            # there is a distribution for this platform. This isn't a big deal, as channels are
            # typically split by platform. If this changes, we would need to re-consider how this
            # is implemented.

            for recipe_pair in recipes:
                meta, dist_location = recipe_pair
                if meta.pkg_fn() in index:
                    recipe_pair[1] = index[meta.pkg_fn()]['channel']
        if self.inspection_directories:
            for directory in self.inspection_directories:
                files = glob.glob(os.path.join(directory, '*.tar.bz2'))
                fnames = [os.path.basename(fpath) for fpath in files]
                for recipe_pair in recipes:
                    meta, dist_location = recipe_pair
                    if dist_location is None and meta.pkg_fn() in fnames:
                        recipe_pair[1] = directory
        return recipes

    def build(self, meta):
        print('Building ', meta.dist())
        with meta.vn_context():
            build.build(meta.meta)

    def main(self):
        recipe_metas = self.fetch_all_metas()
        index = get_index(use_cache=True)

        print('Resolving distributions from {} recipes... '.format(len(recipe_metas)))

        all_distros = []
        for meta in recipe_metas:
            distros = resolved_distribution.ResolvedDistribution.resolve_all(meta, index,
                                                       getattr(self, 'extra_build_conditions', []))
            # TODO: Update the index with the new distros (see https://github.com/pelson/Obvious-CI/issues/25)
            distro_cases = {distro.special_versions: distro for distro in distros}
            cases = list(vn_matrix.keep_top_n_major_versions(distro_cases.keys(), n=self.matrix_max_n_major_minor_versions[0]))
            cases = list(vn_matrix.keep_top_n_minor_versions(cases, n=self.matrix_max_n_major_minor_versions[1]))
            for distro in distros:
                if distro.special_versions in cases:
                    all_distros.append(distro)

        print('Computed that there are {} distributions from the {} '
              'recipes:'.format(len(all_distros), len(recipe_metas)))
        recipes_and_dist_locn = self.find_existing_built_dists(all_distros)

        print('Resolved dependencies, will be built in the following order: \n\t{}'.format(
              '\n\t'.join(['{} (will be built: {})'.format(meta.dist(), dist_locn is None)
                           for meta, dist_locn in recipes_and_dist_locn])))
 
        for meta, built_dist_location in recipes_and_dist_locn:
            if built_dist_location is None:
                built_dist_location = self.build(meta)
            self.post_build(meta, built_dist_location)

    def post_build(self, meta, built_dist_location):
        """
        The post build phase occurs whether or not a build has actually taken place.
        It is the point at which a distribution is transfered to the desired artefact
        location.

        Parameters
        ----------
        meta : MetaData
            The distribution for which we are running the post-build phase
        build_dist_location : str
            The location of the built .tar.bz2 file for the given meta.

        """
        for artefact_destination in self.artefact_destinations:
            print('arti:', artefact_destination)
            #            artefact_destination.make_available(meta, built_dist_location)

