# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from conda import __version__ as CONDA_VERSION

CONDA_VERSION_MAJOR_MINOR = tuple(int(x) for x in CONDA_VERSION.split('.')[:2])

if (4, 3) <= CONDA_VERSION_MAJOR_MINOR < (4, 4):
    from conda.lock import Locked
    from conda.exports import get_index
    from conda.exports import subdir
    from conda.exports import MatchSpec
    from conda.exports import Unsatisfiable
    from conda.exports import NoPackagesFound
    from conda.exports import Resolve
    from conda.exports import string_types
    from conda.models.dist import Dist as _Dist

    def get_key(dist_or_filename):
        return dist_or_filename

    def copy_index(index):
        return {_Dist(key): index[key] for key in index.keys()}

    def ensure_dist_or_dict(fn):
        return _Dist.from_string(fn)

    from conda.console import setup_verbose_handlers
    setup_verbose_handlers()
    from conda.gateways.logging import initialize_logging
    initialize_logging()

elif (4, 2) <= CONDA_VERSION_MAJOR_MINOR < (4, 3):
    from conda.lock import Locked
    from conda.exports import get_index
    from conda.exports import subdir
    from conda.exports import MatchSpec
    from conda.exports import Unsatisfiable
    from conda.exports import NoPackagesFound
    from conda.exports import Resolve
    from conda.exports import string_types

    def get_key(dist_or_filename):
        return dist_or_filename.fn

    def copy_index(index):
        index = index.copy()
        return index

    def ensure_dist_or_dict(fn):
        return fn

    # We need to import conda.fetch and conda.resolve to trigger the
    # creation of the loggers.
    import conda.fetch
    import conda.resolve

else:
    raise NotImplementedError("CONDA_VERSION: %s  CONDA_VERSION_MAJOR_MINOR: %s"
                              % (CONDA_VERSION, str(CONDA_VERSION_MAJOR_MINOR)))


subdir = subdir
Locked = Locked
Resolve, get_index = Resolve, get_index
MatchSpec = MatchSpec
Unsatisfiable, NoPackagesFound = Unsatisfiable, NoPackagesFound
string_types = string_types
