import collections
import os

from conda_build.index import write_repodata
try:
    import conda_build.api
    from conda_build.utils import get_lock
    extra_config = False
except ImportError:
    import conda_build
    extra_config = True

from conda_build_all.conda_interface import subdir

_DummyPackage = collections.namedtuple('_DummyPackage',
                                       ['pkg_name', 'build_deps',
                                        'run_deps', 'vn'])


class DummyPackage(_DummyPackage):
    def __new__(cls, name, build_deps=None, run_deps=None, version='0.0'):
        return super(DummyPackage, cls).__new__(cls, name, build_deps or (),
                                                run_deps or (), version)

    def name(self):
        return self.pkg_name

    def version(self):
        return self.vn

    def dist(self):
        return '{}-{}-{}'.format(self.name(), self.version(), '0')

    def get_value(self, item, default):
        if item == 'requirements/run':
            return self.run_deps
        elif item == 'requirements/build':
            return self.build_deps
        else:
            raise AttributeError(item)

    def __repr__(self):
        # For testing purposes, this is particularly convenient.
        return self.name()


class DummyIndex(dict):
    def add_pkg(self, name, version, build_string='',
                depends=(), build_number='0',
                **extra_items):
        if build_string:
            build_string = '{}_{}'.format(build_string, build_number)
        else:
            build_string = build_number
        pkg_info = dict(name=name, version=version, build_number=build_number,
                        build=build_string, subdir=subdir,
                        depends=tuple(depends), **extra_items)
        self['{}-{}-{}.tar.bz2'.format(name, version, build_string)] = pkg_info

    def add_pkg_meta(self, meta):
        # Add a package given its MetaData instance. This may include a DummyPackage
        # instance in the future.
        if isinstance(meta, DummyPackage):
            raise NotImplementedError('')
        self['{}.tar.bz2'.format(meta.dist())] = meta.info_index()

    def write_to_channel(self, dest):
        # Write the index to a channel. Useful to get conda to read it back in again
        # using conda.api.get_index().
        channel_subdir = os.path.join(dest, subdir)
        if not os.path.exists(channel_subdir):
            os.mkdir(channel_subdir)
        if hasattr(conda_build, 'api'):
            lock = get_lock(channel_subdir)
            write_repodata({'packages': self, 'info': {}}, channel_subdir, lock, config=conda_build.api.Config())
        else:
            write_repodata({'packages': self, 'info': {}}, channel_subdir)

        return channel_subdir

