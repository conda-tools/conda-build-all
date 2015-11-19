from __future__ import print_function

from contextlib import contextmanager
import logging
import os
import subprocess
from argparse import Namespace

from conda.api import get_index
from conda_build.metadata import MetaData
import conda.config
import conda_build.config


#import conda_build_all.logging
import conda_build_all.version_matrix as vn_matrix


@contextmanager
def setup_vn_mtx_case(case):
    orig_npy = conda_build.config.config.CONDA_NPY
    orig_py = conda_build.config.config.CONDA_PY

    for pkg, version in case:
        version = int(version.replace('.', ''))
        if pkg == 'python':
            conda_build.config.config.CONDA_PY = version
        elif pkg == 'numpy':
            conda_build.config.config.CONDA_NPY = version
        else:
            raise NotImplementedError('Package {} not yet implemented.'
                                      ''.format(pkg))
    yield
    conda_build.config.config.CONDA_NPY = orig_npy
    conda_build.config.config.CONDA_PY = orig_py


class ResolvedDistribution(object):
    """
    Represents a conda pacakge, with the appropriate special case
    versions fixed (e.g. CONDA_PY, CONDA_NPY). Without this, a meta
    changes as the conda_build.config.CONDA_NPY changes.

    Parameters
    ----------
    meta: conda_build.metadata.MetData
        The package which has been resolved.
    special_versions: iterable
        A list of the versions which have been resolved for this package.
        e.g. ``(['python', '27'],)``

    """
    def __init__(self, meta, special_versions=()):
        self.meta = meta
        self.special_versions = special_versions

    def __repr__(self):
        return 'BakedDistribution({}, {})'.format(self.meta,
                                                  self.special_versions)

    def __str__(self):
        return self.dist()

    def vn_context(self):
        return setup_vn_mtx_case(self.special_versions)

    def __getattr__(self, name):
        with setup_vn_mtx_case(self.special_versions):
            self.meta.parse_again()
            result = getattr(self.meta, name)

        # Wrap any callable such that it is called within the appropriate
        # environment.
        # callable exists in python 2.* and >=3.2
        if callable(result):
            orig_result = result
            import functools
            @functools.wraps(result)
            def with_vn_mtx_setup(*args, **kwargs):
                with setup_vn_mtx_case(self.special_versions):
                    self.meta.parse_again()
                    return orig_result(*args, **kwargs)
            result = with_vn_mtx_setup
        return result

    @classmethod
    def resolve_all(cls, meta, index=None, extra_conditions=None):
        """
        Given a package, return a list of ResolvedDistributions, one for each
        possible (necessary) version permutation.

        """
        if index is None:
            with vn_matrix.override_conda_logging('WARN'):
                index = get_index()

        cases = vn_matrix.special_case_version_matrix(meta, index)

        if extra_conditions:
            cases = list(vn_matrix.filter_cases(cases, extra_conditions))
        result = []
        for case in cases:
            dist = cls(meta, case)
            if not dist.skip():
                result.append(dist)
        return result


