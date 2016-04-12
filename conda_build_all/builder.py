"""
Build all the conda recipes in the given directory sequentially if they do not
already exist on the given binstar channel.
Building is done in order of dependencies (circular dependencies are not supported).
Once a build is complete, the distribution will be uploaded (provided BINSTAR_TOKEN is
defined), and the next package will be processed.

"""
from __future__ import print_function

from copy import deepcopy
import glob
import logging
import mock
import os
import subprocess
from argparse import Namespace

from binstar_client.utils import get_binstar
import binstar_client
from conda.api import get_index
import conda.config
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


def list_metas(directory, max_depth=0):
    """
    Get the build metadata of all recipes in a directory.

    The order of metas from this function is not guaranteed.

    Parameters
    ----------
    directory
        Where to start looking for metas using os.walk.
    max_depth : int
        How deep to recurse when looking for recipes. 
        A value ``<=0`` will recurse indefinitely. A value of 1
        will look in the given directory for a meta.yaml.
        (default: 0)

    """
    packages = []
    current_depth = max_depth
    root = os.path.normpath(directory)
    for new_root, dirs, files in os.walk(root, followlinks=True):
        depth = new_root[len(root):].count(os.path.sep) + 1
        if max_depth > 0 and depth >= max_depth:
            del dirs[:]
 
        if 'meta.yaml' in files:
            packages.append(MetaData(new_root))
    return packages


def sort_dependency_order(metas):
    """Sort the metas into the order that they must be built."""
    meta_named_deps = {}
    buildable = [meta.name() for meta in metas]
    for meta in metas:
        meta = deepcopy(meta)

        # In order to deal with selectors impacting sort order, we completely
        # ignore them for the sake of ordering. This decision was taken in the
        # light of https://github.com/SciTools/conda-build-all/issues/30 as a
        # pragmatic performance choice.
        def select_lines(data, *args, **kwargs):
            # Just return the data without removing any of the lines. This
            # is only a suitable solution when selectors are also comments.
            return data
        with mock.patch('conda_build.metadata.select_lines', new=select_lines):
            meta.parse_again()

        # Now that we have re-parsed the metadata with selectors unconditionally
        # included, we can get the run and build dependencies and do a toposort.
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

        Parameters
        ----------
        conda_recipes_directory : string
            The path to the directory in which to look for conda recipes.
        inspection_channels : iterable
            The conda channels to inspect to determine whether a recipe has already been built.
        inspection_directories : iterable
            The local directories to inspect to determine whether a recipe has already been built.
        artefact_destinations : iterable of conda_build_all.artefact_destination.ArtefactDestination
            The destinations for the built artefact to go to.
        matrix_conditions : iterable of conda specifications
            The conditions to apply when determining whether a recipe should be built
        matrix_max_n_major_minor_versions : pair of ints
            The number of major and minor versions to preserve for each resolved recipe. For instance,
            if a recipe can be built against np 1.7, 1.8 and 1.9, and the number of minor versions is 2,
            the build matrix will prune the 1.7 option.

        """
        self.conda_recipes_directory = conda_recipes_directory
        self.inspection_channels = inspection_channels or []
        self.inspection_directories = inspection_directories
        self.artefact_destinations = artefact_destinations
        self.matrix_conditions = matrix_conditions
        self.matrix_max_n_major_minor_versions = matrix_max_n_major_minor_versions

    def fetch_all_metas(self):
        """
        Return the conda recipe metas, in the order they should be built.

        """
        conda_recipes_directory = os.path.abspath(os.path.expanduser(self.conda_recipes_directory))
        recipe_metas = list_metas(conda_recipes_directory)
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
            return bldpkg_path(build.build(meta.meta))

    def compute_build_distros(self, index, recipes):
        """
        Given the recipes which are to be built, return a list of BakedDistribution instances
        for all distributions that should be built.

        """
        all_distros = []
        index = index.copy()
        for meta in recipes:
            distros = resolved_distribution.ResolvedDistribution.resolve_all(meta, index,
                                                                             self.matrix_conditions)
            cases = [distro.special_versions for distro in distros]
            cases = list(vn_matrix.keep_top_n_major_versions(cases, n=self.matrix_max_n_major_minor_versions[0]))
            cases = list(vn_matrix.keep_top_n_minor_versions(cases, n=self.matrix_max_n_major_minor_versions[1]))
            for distro in distros:
                if distro.special_versions in cases:
                    # Update the index with this distribution so that it can be considered by the version matrix.
                    if distro.pkg_fn() not in index:
                        index[distro.pkg_fn()] = distro.info_index()
                    all_distros.append(distro)

        return all_distros

    def main(self):
        recipe_metas = self.fetch_all_metas()
        index = get_index(use_cache=True)

        print('Resolving distributions from {} recipes... '.format(len(recipe_metas)))

        all_distros = self.compute_build_distros(index, recipe_metas)
        print('Computed that there are {} distributions from the {} '
              'recipes:'.format(len(all_distros), len(recipe_metas)))
        recipes_and_dist_locn = self.find_existing_built_dists(all_distros)

        print('Resolved dependencies, will be built in the following order: \n\t{}'.format(
              '\n\t'.join(['{} (will be built: {})'.format(meta.dist(), dist_locn is None)
                           for meta, dist_locn in recipes_and_dist_locn])))
 
        for meta, built_dist_location in recipes_and_dist_locn:
            was_built = built_dist_location is None
            if was_built:
                built_dist_location = self.build(meta)
            self.post_build(meta, built_dist_location, was_built)

    def post_build(self, meta, built_dist_location, was_built):
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
            artefact_destination.make_available(meta, built_dist_location, was_built)

