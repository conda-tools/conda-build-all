# NOTE: This module has no unit tests.

from __future__ import print_function

import os
import shutil

import conda_build.build as build_module
from conda_build.metadata import MetaData
import conda_build.config
from conda.lock import Locked

try:
    from conda_build.api import get_output_file_path
except ImportError:
    from conda_build.build import bldpkg_path as get_output_file_path

import conda_build.source
import binstar_client
from binstar_client.utils.detect import detect_package_type, get_attrs

from . import inspect_binstar


def build(meta, test=True):
    """Build (and optionally test) a recipe directory."""
    with Locked(conda_build.config.croot):
        # Check whether verbose is a module-level variable in
        # this version of conda_build and set it properly if it is.
        if 'verbose' in dir(build_module):
            build_module.verbose = False
            kwd = {}
        else:
            kwd = {'verbose': False}
        meta.check_fields()

        if os.path.exists(conda_build.source.WORK_DIR):
            shutil.rmtree(conda_build.source.WORK_DIR)
        build_module.build(meta, post=None, need_source_download=True, **kwd)
        if test:
            build_module.test(meta, **kwd)
        return meta


def upload(cli, meta, owner, channels=['main'], config=None):
    """Upload a distribution, given the build metadata."""
    fname = get_output_file_path(meta)
    package_type = detect_package_type(fname)
    package_attrs, release_attrs, file_attrs = get_attrs(package_type, fname)
    package_name = package_attrs['name']
    version = release_attrs['version']

    # Check the package exists, otherwise create one.
    try:
        cli.package(owner, package_name)
    except binstar_client.NotFound:
        print('Creating the {} package on {}'.format(package_name, owner))
        summary = package_attrs['summary']
        cli.add_package(owner, package_name, summary, package_attrs.get('license'), public=True)

    # Check the release exists, otherwise create one.
    try:
        cli.release(owner, package_name, version)
    except binstar_client.NotFound:
        # TODO: Add readme.md support for descriptions?
        cli.add_release(owner, package_name, version, requirements=[], announce=None,
                        description='')

    try:
        cli.distribution(owner, package_name, version, file_attrs['basename'])
    except binstar_client.NotFound:
        # The file doesn't exist.
        pass
    else:
        print('Distribution %s already exists ... removing' % (file_attrs['basename'],))
        cli.remove_dist(owner, package_name, version, file_attrs['basename'])

    with open(fname, 'rb') as fd:
        print('\nUploading file %s/%s/%s/%s to %s...' % (owner, package_name, version, file_attrs['basename'], channels))
        upload_info = cli.upload(owner, package_name, version, file_attrs['basename'],
                                 fd, package_type, description='',
                                 dependencies=file_attrs.get('dependencies'),
                                 attrs=file_attrs['attrs'],
                                 channels=channels)
        return upload_info
