from contextlib import contextmanager
from collections import defaultdict
import logging

import conda.resolve
from conda.resolve import MatchSpec
from conda.resolve import stdoutlog
from conda.console import SysStdoutWriteHandler

try:
    import conda_build.api
except ImportError:
    import conda_build.config


conda_stdoutlog = stdoutlog

NO_PACKAGES_EXCEPTION = tuple(getattr(conda.resolve, attr)
                              for attr in ['Unsatisfiable', 'NoPackagesFound'])

class StdoutNewline(SysStdoutWriteHandler):
    def emit(self, record):
        record.msg += '\n'
        SysStdoutWriteHandler.emit(self, record)


stdout = logging.getLogger('conda_build_all.version_matrix.stdoutlog')
stdout.addHandler(StdoutNewline())
stdout.setLevel(logging.WARNING)


@contextmanager
def override_conda_logging(level):
    # Override the conda logging handlers.

    # We need to import conda.fetch and conda.resolve to trigger the
    # creation of the loggers in the first place.
    import conda.fetch
    import conda.resolve

    levels = {}
    handlers = {}
    loggers = ['progress', 'progress.start', 'progress.update',
               'progress.stop', 'stdoutlog', 'stderrlog',
               'conda.resolve', 'dotupdate']

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        levels[logger_name] = logger.level
        handlers[logger_name] = logger.handlers

        logger.setLevel(level)
        logger.handlers = []
    yield
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(levels[logger_name])
        logger.handlers = handlers[logger_name]


def conda_special_versions(meta, index, version_matrix=None):
    """
    Returns a generator which configures conda build's PY and NPY versions
    according to the given version matrix. If no version matrix is given, it
    will be computed by :func:`special_case_version_matrix`.

    """
    if version_matrix is None:
        version_matrix = special_case_version_matrix(meta, index)

    for case in version_matrix:
        config = setup_vn_mtx_case(case)
        yield config


def parse_specifications(requirements):
    """
    Parse a list of specifications, turning multi-line specifications into
    a single specification.
    """
    requirement_specs = defaultdict(list)
    # Generate a list of requirements for each spec name to ensure that
    # multi-line specs are handled.
    for spec in requirements:
        spec_details = spec.split(None, 1)
        if len(spec_details) == 2:
            # Package name and version spec were given, append the
            # version spec.
            requirement_specs[MatchSpec(spec).name].append(spec_details[1])
        elif spec_details[0] not in requirement_specs:
            # Only package name given (e.g. 'numpy'), and the package name is
            # not in the requirements yet, so add an empty list.
            requirement_specs[MatchSpec(spec).name] = []

    # Combine multi-line specs into a single line by assuming the requirements
    # should be and-ed.
    for spec_name, spec_list in requirement_specs.items():
        requirement_specs[spec_name] = ','.join(spec_list)

    # Turn these into MatchSpecs.
    requirement_specs = {name: MatchSpec(' '.join([name, spec]).strip())
                         for name, spec in requirement_specs.items()}

    return requirement_specs


def special_case_version_matrix(meta, index):
    """
    Return the non-orthogonal version matrix for special software within conda
    (numpy, python).

    For example, supposing a meta depended on numpy and python, and that there
    was a numpy 1.8 & 1.9 for python 2.7 but only a numpy 1.9 for python 3.5,
    the matrix should be:

        ([('python', '2.7'), ('numpy', '1.8')],
         [('python', '2.7'), ('numpy', '1.9')],
         [('python', '3.5'), ('numpy', '1.9')])

    Packages which don't depend on any of the special cases will return an
    iterable with an empty tuple. This is analogous to saying "a build is needed,
    but there are no special cases". Thus, code may reliably implement a loop such as:

    for case in special_case_version_matrix(...):
        ... setup the case ...
        ... build ...

    """
    try:
        from conda.models.dist import Dist
        index = {Dist(key): index[key] for key in index.keys()}
        def get_key(dist_or_filename):
            return dist_or_filename
    except ImportError:
        def get_key(dist_or_filename):
            return dist_or_filename.fn
    r = conda.resolve.Resolve(index)

    requirements = meta.get_value('requirements/build', [])
    requirement_specs = parse_specifications(requirements)

    run_requirements = meta.get_value('requirements/run', [])
    run_requirement_specs = parse_specifications(run_requirements)

    # Thanks to https://github.com/conda/conda-build/pull/493 we no longer need to
    # compute the complex matrix for numpy versions unless a specific version has
    # been defined.
    np_spec = requirement_specs.get('numpy')
    np_run_spec = run_requirement_specs.get('numpy')
    if np_spec and np_run_spec and 'x.x' not in np_run_spec.spec:
        # A simple spec (just numpy) has been defined, so we can drop it from the
        # special cases.
        requirement_specs.pop('numpy')

    for pkg in requirement_specs:
        spec = requirement_specs[pkg]
        # We want to bake the version in, but we don't know what it is yet.
        if 'x.x' in spec.spec:
            # Remove the x.x part of the specification, assuming that if it
            # is present with other specifications they are and-ed together,
            # i.e. comma-separated.
            name, specification = spec.spec.split()
            spec_list = specification.split(',')
            no_xx = [s for s in spec_list if s != 'x.x']
            new_spec = ','.join(no_xx)
            if new_spec:
                ms = MatchSpec(' '.join([name, new_spec]))
            else:
                ms = MatchSpec(name)
            requirement_specs[pkg] = ms

    def minor_vn(version_str):
        """
        Take an string of the form 1.8.2, into string form 1.8
        """
        return '.'.join(version_str.split('.')[:2])

    cases = set()
    unsolvable_cases = set()

    def get_pkgs(spec):
        try:
            # should be r.get_dists_for_spec(spec) for conda-4.3+
            return r.get_pkgs(spec)
        except NO_PACKAGES_EXCEPTION:
            # If no package is found in the channel, we do nothing
            # this is reasonable because add_case_if_soluble does the same
            # for concrete cases.
            # This behavior is important because otherwise this will crash if
            # a package is not available for a certain platform (e.g. win).
            return []

    def add_case_if_soluble(case):
        # Whilst we strictly don't need to, shortcutting cases we've already seen makes a
        # *huge* performance difference.
        if case in cases | unsolvable_cases:
            return

        specs = ([ms.spec for ms in requirement_specs.values()] +
                 ['{} {}*'.format(pkg, version) for pkg, version in case])

        try:
            # Figure out if this case is actually resolvable. We don't care how,
            # just that it could be.
            r.solve(specs)
        except NO_PACKAGES_EXCEPTION:
            unsolvable_cases.add(case)
        else:
            cases.add(case)

    with override_conda_logging(logging.WARN):
        if 'numpy' in requirement_specs:
            np_spec = requirement_specs.pop('numpy')
            py_spec = requirement_specs.pop('python', None)
            for numpy_pkg in get_pkgs(np_spec):
                np_vn = minor_vn(index[get_key(numpy_pkg)]['version'])
                numpy_deps = index[get_key(numpy_pkg)]['depends']
                numpy_deps = {MatchSpec(spec).name: MatchSpec(spec)
                              for spec in numpy_deps}
                # This would be problematic if python wasn't a dep of numpy.
                for python_pkg in get_pkgs(numpy_deps['python']):
                    if py_spec and not py_spec.match(get_key(python_pkg)):
                        continue
                    py_vn = minor_vn(index[get_key(python_pkg)]['version'])
                    case = (('python', py_vn),
                            ('numpy', np_vn),
                            )
                    add_case_if_soluble(case)
        elif 'python' in requirement_specs:
            py_spec = requirement_specs.pop('python')
            for python_pkg in get_pkgs(py_spec):
                py_vn = minor_vn(index[get_key(python_pkg)]['version'])
                case = (('python', py_vn), )
                add_case_if_soluble(case)

        if 'perl' in requirement_specs:
            pl_spec = requirement_specs.pop('perl')
            for case_base in list(cases or [()]):
                for perl_pkg in get_pkgs(pl_spec):
                    pl_vn = index[get_key(perl_pkg)]['version']
                    case = case_base + (('perl', pl_vn), )
                    add_case_if_soluble(case)
                if case_base in cases:
                    cases.remove(case_base)

        if 'r-base' in requirement_specs:
            r_spec = requirement_specs.pop('r-base')
            for case_base in list(cases or [()]):
                for r_pkg in get_pkgs(r_spec):
                    r_vn = index[get_key(r_pkg)]['version']
                    case = case_base + (('r-base', r_vn), )
                    add_case_if_soluble(case)
                if case_base in cases:
                    cases.remove(case_base)

    # Deal with the fact that building a Python recipe itself requires a special case
    # version. This comes down to the odd decision in
    # https://github.com/conda/conda-build/commit/3dddeaf3cf5e85369e28c8f96e24c2dd655e36f0.
    if meta.name() == 'python' and not cases:
        cases.add((('python', '.'.join(meta.version().split('.', 2)[:2])),))

    # Put an empty case in to allow simple iteration of the results.
    if not cases:
        cases.add(())

    return set(cases)

def _ensure_dist_or_dict(fn):
    try:
        from conda.models.dist import Dist
        return Dist.from_string(fn)
    except ImportError:
        return fn

def filter_cases(cases, extra_specs):
    """
    cases might look like:

        cases = ([('python', '2.7'), ('numpy', '1.8')],
                 [('python', '2.7'), ('numpy', '1.9')],
                 [('python', '3.5'), ('numpy', '1.8')],
                 )

    Typically extra_specs comes from the environment specification.

    """
    specs = [MatchSpec(spec) for spec in extra_specs]

    for case in cases:
        # Invent a sensible "tar.bz2" name which we can use to invoke conda's
        # MatchSpec matching.
        cases_by_pkg_name = {name: '{}-{}.0-0.tar.bz2'.format(name, version)
                             for name, version in case}
        match = []
        for spec in specs:
            # Only run the filter on the packages in cases.
            if spec.name in cases_by_pkg_name:
                match.append(bool(spec.match(_ensure_dist_or_dict(cases_by_pkg_name[spec.name]))))
        if all(match):
            yield case


def keep_top_n_major_versions(cases, n=2):
    """
    Remove all but the top n major version cases for each package in cases.

    Parameters
    ----------
    cases
        The cases to filter. See filter_cases for a definition of cases.
    n : integer >= 0
        The number of major versions to keep. Default is ``2``. 0 results in all
        major versions being kept.

    """
    name_to_major_versions = {}
    for case in cases:
        for name, version in case:
            name_to_major_versions.setdefault(name, set()).add(int(version.split('.')[0]))
    cutoff = {name: sorted(majors)[-n:] for name, majors in name_to_major_versions.items()}
    for case in cases:
        keeper = True
        for name, version in case:
            if int(version.split('.')[0]) not in cutoff[name]:
                keeper = False
        if keeper:
            yield case


def keep_top_n_minor_versions(cases, n=2):
    """
    Remove all but the top n minor version cases for each package in cases.
    This will not do any major version filtering, so two major versions with
    many minor versions will result in n x 2 cases returned.

    Parameters
    ----------
    cases
        The cases to filter. See filter_cases for a definition of cases.
    n : integer >= 0
        The number of minor versions to keep. Default is ``2``. 0 results in all
        minor versions being kept.

    """
    mapping = {}
    for case in cases:
        for name, version in case:
            major = int(version.split('.')[0])
            minor = int(version.split('.')[1])
            mapping.setdefault((name, major), set()).add(minor)
    cutoff = {key: sorted(minors)[-n:] for key, minors in mapping.items()}
    for case in cases:
        keeper = True
        for name, version in case:
            major = int(version.split('.')[0])
            minor = int(version.split('.')[1])
            if minor not in cutoff[(name, major)]:
                keeper = False
        if keeper:
            yield case

if hasattr(conda_build, 'api'):
    def setup_vn_mtx_case(case, config):
        for pkg, version in case:
            if pkg == 'python':
                version = int(version.replace('.', ''))
                config.CONDA_PY = version
            elif pkg == 'numpy':
                version = int(version.replace('.', ''))
                config.CONDA_NPY = version
            elif pkg == 'perl':
                config.CONDA_PERL = version
            elif pkg == 'r-base':
                config.CONDA_R = version
            else:
                raise NotImplementedError('Package {} not yet implemented.'
                                          ''.format(pkg))
        return config

else:
    @contextmanager
    def setup_vn_mtx_case(case, config=None):
        config = conda_build.config.config
        orig_npy = conda_build.config.config.CONDA_NPY
        orig_py = conda_build.config.config.CONDA_PY
        orig_r = conda_build.config.config.CONDA_R
        orig_perl = conda_build.config.config.CONDA_PERL
        for pkg, version in case:
            if pkg == 'python':
                version = int(version.replace('.', ''))
                config.CONDA_PY = version
            elif pkg == 'numpy':
                version = int(version.replace('.', ''))
                config.CONDA_NPY = version
            elif pkg == 'perl':
                config.CONDA_PERL = version
            elif pkg == 'r-base':
                config.CONDA_R = version
            else:
                raise NotImplementedError('Package {} not yet implemented.'
                                          ''.format(pkg))
        yield
        conda_build.config.config.CONDA_NPY = orig_npy
        conda_build.config.config.CONDA_PY = orig_py
        conda_build.config.config.CONDA_R = orig_r
        conda_build.config.config.CONDA_PERL = orig_perl
