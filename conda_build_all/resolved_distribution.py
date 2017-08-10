from __future__ import print_function

from .conda_interface import get_index
import conda_build.config


#import conda_build_all.logging
import conda_build_all.version_matrix as vn_matrix
from conda_build_all.version_matrix import setup_vn_mtx_case


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

    def vn_context(self, config=None):
        return setup_vn_mtx_case(self.special_versions, config)

    def __getattr__(self, name):
        if hasattr(self.meta, 'config'):
            config = setup_vn_mtx_case(self.special_versions,
                                       config=self.meta.config)
            self.meta.parse_again(config)
        else:
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
                if hasattr(self.meta, 'config'):
                    config = setup_vn_mtx_case(self.special_versions,
                                               config=self.meta.config)
                    self.meta.parse_again(config=config)
                    return orig_result(*args, **kwargs)
                else:
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

        cases = sorted(vn_matrix.special_case_version_matrix(meta, index))

        if extra_conditions:
            cases = list(vn_matrix.filter_cases(cases, extra_conditions))
        result = []
        for case in cases:
            dist = cls(meta, case)
            if not dist.skip():
                result.append(dist)
        return result
