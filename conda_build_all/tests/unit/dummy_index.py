import collections
import conda.config


_DummyPackage = collections.namedtuple('_DummyPackage',
                                       ['pkg_name', 'build_deps', 'run_deps'])


class DummyPackage(_DummyPackage):
    def __new__(cls, name, build_deps=None, run_deps=None):
        return super(DummyPackage, cls).__new__(cls, name, build_deps or (),
                                                run_deps or ())

    def name(self):
        return self.pkg_name

    def dist(self):
        return '{}-{}-{}'.format(self.name(), '0.0', '0')

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
                        build=build_string, subdir=conda.config.subdir,
                        depends=tuple(depends), **extra_items)
        self['{}-{}-{}.tar.bz2'.format(name, version, build_string)] = pkg_info
