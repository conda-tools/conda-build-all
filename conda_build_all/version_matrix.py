# TODO: Pull this back together with conda_manifest.
import os
from contextlib import contextmanager
from collections import defaultdict

import conda.resolve
from conda.resolve import MatchSpec
import conda_build.config
# import conda_manifest.config

import logging
from conda.resolve import stdoutlog, dotlog

conda_stdoutlog = stdoutlog
# TODO: Handle the amount of standard out that conda is producing.


from conda.console import SysStdoutWriteHandler


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
        with setup_vn_mtx_case(case):
            yield case


def parse_specifications(requirements):
    """
    Parse a list of specifications, turning multi-line specifications into
    a single specification.
    """
    requirement_specs = defaultdict(list)
    # Generate a list of requirements for each spec name to ensure that
    # multi-line specs are handled.
    for spec in requirements:
        spec_details = spec.split()
        if len(spec_details) == 2:
            # Package name and version spec were given, append the
            # version spec.
            requirement_specs[MatchSpec(spec).name].append(spec_details[1])
        elif len(spec_details) == 1:
            # Only package name given (e.g. 'numpy'), so an empty list works.
            requirement_specs[MatchSpec(spec).name] = []
        else:
            # Three-part specification, which includes a build string. Add
            # both the second and third part to the list.
            full_spec = ' '.join(spec_details[1:])
            requirement_specs[MatchSpec(spec).name].append(full_spec)

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

    .. note::

        This algorithm does not deal with PERL and R versions at this time, and may be
        extended in the future to compute other special case dimensions (e.g. features).

    """
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
        Take an string of the form 1.8.2, into integer form 1.8
        """
        return '.'.join(version_str.split('.')[:2])

    cases = set()
    unsolvable_cases = set()

    def add_case_if_soluble(case):
        # Whilst we strictly don't need to, shortcutting cases we've already seen makes a
        # *huge* performance difference.
        if case in cases | unsolvable_cases:
            return

        specs = ([ms.spec for ms in requirement_specs.values()] +
                 ['{} {}.*'.format(pkg, version) for pkg, version in case])
        cases.add(case)
        return
        # This code path is disabled for now as it takes a prohibitive amount of time to compute.
        try:
            # Figure out if this case is actually resolvable. We don't care how,
            # just that it could be.
            r.solve2(specs, features=set(), guess=False, unsat_only=True)
        except RuntimeError:
            unsolvable_cases.add(case)
        else:
            cases.add(case)

    with override_conda_logging(logging.WARN):
        if 'numpy' in requirement_specs:
            np_spec = requirement_specs.pop('numpy')
            py_spec = requirement_specs.pop('python', None)
            for numpy_pkg in r.get_pkgs(np_spec):
                np_vn = minor_vn(index[numpy_pkg.fn]['version'])
                numpy_deps = index[numpy_pkg.fn]['depends']
                numpy_deps = {MatchSpec(spec).name: MatchSpec(spec)
                              for spec in numpy_deps}
                # This would be problematic if python wasn't a dep of numpy.
                for python_pkg in r.get_pkgs(numpy_deps['python']):
                    if py_spec and not py_spec.match(python_pkg.fn):
                        continue
                    py_vn = minor_vn(index[python_pkg.fn]['version'])
                    case = (('python', py_vn),
                            ('numpy', np_vn),
                            )
                    add_case_if_soluble(case)
        elif 'python' in requirement_specs:
            py_spec = requirement_specs.pop('python')
            for python_pkg in r.get_pkgs(py_spec):
                py_vn = minor_vn(index[python_pkg.fn]['version'])
                case = (('python', py_vn), )
                add_case_if_soluble(case)

        if 'perl' in requirement_specs:
            raise NotImplementedError('PERL version matrix not yet implemented.')
        if 'r' in requirement_specs:
            raise NotImplementedError('R version matrix not yet implemented.')

    # Deal with the fact that building a Python recipe itself requires a special case
    # version. This comes down to the odd decision in
    # https://github.com/conda/conda-build/commit/3dddeaf3cf5e85369e28c8f96e24c2dd655e36f0.
    if meta.name() == 'python' and not cases:
        cases.add((('python', meta.version()),))

    # Put an empty case in to allow simple iteration of the results.
    if not cases:
        cases.add(())

    return set(cases)


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
                match.append(bool(spec.match(cases_by_pkg_name[spec.name])))
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

