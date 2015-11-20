import os


def resolve_dependencies(package_dependencies):
    """
    Given a dictionary mapping a package to its dependencies, return a
    generator of packages to install, sorted by the required install
    order.

    >>> deps = resolve_dependencies({'a': ['b', 'c'], 'b': ['c'],
                                     'c': ['d'], 'd': []})
    >>> list(deps)
    ['d', 'c', 'b', 'a']

    """
    remaining_dependencies = package_dependencies.copy()
    completed_packages = []

    # A maximum of 10000 iterations. Beyond that and there is probably a
    # problem.
    for failsafe in range(10000):
        for package, deps in sorted(remaining_dependencies.copy().items()):
            if all(dependency in completed_packages for dependency in deps):
                completed_packages.append(package)
                remaining_dependencies.pop(package)
                yield package
            else:
                # Put a check in to ensure that all the dependencies were
                # defined as packages, otherwise we will never succeed.
                for dependency in deps:
                    if dependency not in package_dependencies:
                        msg = ('The package {} depends on {}, but it was not '
                               'part of the package_dependencies dictionary.'
                               ''.format(package, dependency))
                        raise ValueError(msg)

        # Close off the loop if we've completed the dependencies.
        if not remaining_dependencies:
            break
    else:
        raise ValueError('Dependencies could not be resolved. '
                         'Remaining dependencies: {}'
                         ''.format(remaining_dependencies))
