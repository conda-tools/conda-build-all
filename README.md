conda build-all
===============

``conda build-all`` is a conda subcommand which allows multiple distributions to be built (and uploaded) in a single command.
It makes use of the underlying machinery developed for ``conda build``, but has a number of advantages:

 * Automatically computes a build matrix for a single package, and builds all possible combinations.
 * Can be given a directory of recipes, each of which will be identified and built (with each having their own build matrix).
 * Will resolve the build order based on the dependency graph from both build and run time dependencies.
 * Ability to re-build everything, or only build distributions that don't already exist in a conda channel and/or folder.
 * Since the build matrix is computed, ``conda build-all`` avoids the need for special environment variables which control the build.
 * Provides a Python interface for advanced build requirements.

Installation
============
Will eventually be installable with:

```
conda install conda-build-all -c conda-forge
```

In the meantime, please see the conda-build-all.recipe in the root of the conda-build-all repository.


Usage
======

```
usage: conda-buildall [-h]
                      [--inspect-channel [INSPECT_CHANNEL [INSPECT_CHANNEL ...]]]
                      [--inspect-directory [INSPECT_DIRECTORY [INSPECT_DIRECTORY ...]]]
                      [--upload-channel [UPLOAD_CHANNEL [UPLOAD_CHANNEL ...]]]
                      [--matrix-conditions [EXTRA_BUILD_CONDITIONS [EXTRA_BUILD_CONDITIONS ...]]]
                      [--matrix-max-n-major-versions MATRIX_MAX_N_MAJOR_VERSIONS]
                      [--matrix-max-n-minor-versions MATRIX_MAX_N_MINOR_VERSIONS]
                      recipes

Build many conda distributions.

positional arguments:
  recipes               The folder containing conda recipes to build.

optional arguments:
  -h, --help            show this help message and exit
  --inspect-channel [INSPECT_CHANNEL [INSPECT_CHANNEL ...]]
                        Skip a build if the equivalent disribution is already
                        available in the specified channel.
  --inspect-directory [INSPECT_DIRECTORY [INSPECT_DIRECTORY ...]]
                        Skip a build if the equivalent disribution is already
                        available in the specified directory.
  --upload-channel [UPLOAD_CHANNEL [UPLOAD_CHANNEL ...]]
                        The channel(s) to upload built distributions to. It is
                        rare to specify this without the --inspect-channel
                        argument. If a file:// channel, the build will be
                        copied to the directory. If a url:// channel, the
                        build will be uploaded with the anaconda client
                        functionality.
  --matrix-conditions [EXTRA_BUILD_CONDITIONS [EXTRA_BUILD_CONDITIONS ...]]
                        Extra conditions for computing the build matrix.
  --matrix-max-n-major-versions MATRIX_MAX_N_MAJOR_VERSIONS
                        When computing the build matrix, limit to the latest n
                        major versions (0 makes this unlimited). For example,
                        if Python 1, 2 and Python 3 are resolved by the recipe
                        and associated matrix conditions, only the latest N
                        major version will be used for the build matrix.
                        (default: 2)
  --matrix-max-n-minor-versions MATRIX_MAX_N_MINOR_VERSIONS
                        When computing the build matrix, limit to the latest n
                        minor versions (0 makes this unlimited). Note that
                        this does not limit the number of major versions (see
                        also matrix-max-n-major-version). For example, if
                        Python 2 and Python 3 are resolved by the recipe and
                        associated matrix conditions, a total of Nx2 builds
                        will be identified. (default: 2)
```
