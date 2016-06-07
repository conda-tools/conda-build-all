# NOTE: This module has no unit tests.

import conda.config
import binstar_client
from conda_build.build import bldpkg_path
from conda.api import get_index


def distribution_exists(binstar_cli, owner, metadata):
    """
    Determine whether a distribution exists.

    This does not check specific channels - it is either on binstar or it is not.
    """
    fname = '{}/{}.tar.bz2'.format(conda.config.subdir, metadata.dist())
    try:
        r = binstar_cli.distribution(owner, metadata.name(), metadata.version(),
                                     fname)
        exists = True
    except binstar_client.NotFound:
        exists = False
    return exists


def distribution_exists_on_channel(binstar_cli, owner, metadata, channel='main'):
    """
    Determine whether a distribution exists on a specific channel.

    Note from @pelson: As far as I can see, there is no easy way to do this on binstar.

    """
    fname = '{}.tar.bz2'.format(metadata.dist())
    channel_url = '/'.join([owner, 'label', channel])

    distributions_on_channel = get_index([channel_url],
                                         prepend=False, use_cache=False)

    try:
        on_channel = (distributions_on_channel[fname]['subdir'] ==
                      conda.config.subdir)
    except KeyError:
        on_channel = False
    return on_channel


def add_distribution_to_channel(binstar_cli, owner, metadata, channel='main'):
    """
    Add a(n already existing) distribution on binstar to another channel.

    Note - the addition is done based on name and version - no build strings etc.
    so if you have a foo-0.1-np18 and foo-0.1-np19 *both* will be added to the channel.

    """
    package_fname = '{}/{}.tar.bz2'.format(conda.config.subdir, metadata.dist())
    binstar_cli.add_channel(channel, owner, metadata.name(), metadata.version())#filename=package_fname)


def copy_distribution_to_owner(binstar_cli, source_owner, dest_owner,
                               metadata, channel='main'):
    """
    Copy an already existing distribution from one owner to another on
    anaconda.
    """
    package_fname = '{}/{}.tar.bz2'.format(conda.config.subdir, metadata.dist())
    binstar_cli.copy(source_owner, metadata.name(), metadata.version(),
                     basename=package_fname, to_owner=dest_owner,
                     to_channel=channel)
