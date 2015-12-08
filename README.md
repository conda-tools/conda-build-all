conda build-all
===============

``conda build-all`` is a conda subcommand which allows multiple distributions to be built (and uploaded) in a single command.
It makes use of the underlying machinery developed for ``conda build``, but has a number of advantages:

 * Automatically computes a build matrix for a single package, and builds all possible combinations.
 * Can be given a directory of recipes, each of which will be identified and built (with each having their own build matrix).
 * Will resolve the build order based on the dependency graph from both build and run time dependencies.
 * Ability to re-build everything, or only build distributions that don't already exist in a conda channel and/or folder.
 * Since the build matrix is computed, ``conda build-all`` avoids the need for special environment variables which control the build.
 * Provides a Python API for building programmatically.


Installation
============

The easiest way of installing ``conda-build-all`` is with conda, and the ``conda-forge`` channel:

```
conda install conda-build-all --channel conda-forge
```

Building from source is trivial with the pre-requisite dependencies (see ``requirements.txt``).


Usage
======

```
usage: conda-build-all [-h] [--version]
                       [--inspect-channels [INSPECT_CHANNELS [INSPECT_CHANNELS ...]]]
                       [--inspect-directories [INSPECT_DIRECTORIES [INSPECT_DIRECTORIES ...]]]
                       [--no-inspect-conda-bld-directory]
                       [--artefact-directory ARTEFACT_DIRECTORY]
                       [--upload-channels [UPLOAD_CHANNELS [UPLOAD_CHANNELS ...]]]
                       [--matrix-conditions [MATRIX_CONDITIONS [MATRIX_CONDITIONS ...]]]
                       [--matrix-max-n-major-versions MATRIX_MAX_N_MAJOR_VERSIONS]
                       [--matrix-max-n-minor-versions MATRIX_MAX_N_MINOR_VERSIONS]
                       recipes

Build many conda distributions.

positional arguments:
  recipes               The folder containing conda recipes to build.

optional arguments:
  -h, --help            show this help message and exit
  --version             Show conda-build-all's version, and exit.
  --inspect-channels [INSPECT_CHANNELS [INSPECT_CHANNELS ...]]
                        Skip a build if the equivalent disribution is already
                        available in the specified channel.
  --inspect-directories [INSPECT_DIRECTORIES [INSPECT_DIRECTORIES ...]]
                        Skip a build if the equivalent disribution is already
                        available in the specified directory.
  --no-inspect-conda-bld-directory
                        Do not add the conda-build directory to the inspection
                        list.
  --artefact-directory ARTEFACT_DIRECTORY
                        A directory for any newly built distributions to be
                        placed.
  --upload-channels [UPLOAD_CHANNELS [UPLOAD_CHANNELS ...]]
                        The channel(s) to upload built distributions to
                        (requires BINSTAR_TOKEN envioronment variable).
  --matrix-conditions [MATRIX_CONDITIONS [MATRIX_CONDITIONS ...]]
                        Extra conditions for computing the build matrix (e.g.
                        'python 2.7.*'). When set, the defaults for matrix-
                        max-n-major-versions and matrix-max-n-minor-versions
                        are set to 0 (i.e. no limit on the max n versions).
  --matrix-max-n-major-versions MATRIX_MAX_N_MAJOR_VERSIONS
                        When computing the build matrix, limit to the latest n
                        major versions (0 makes this unlimited). For example,
                        if Python 1, 2 and Python 3 are resolved by the recipe
                        and associated matrix conditions, only the latest N
                        major version will be used for the build matrix.
                        (default: 2 if no matrix conditions)
  --matrix-max-n-minor-versions MATRIX_MAX_N_MINOR_VERSIONS
                        When computing the build matrix, limit to the latest n
                        minor versions (0 makes this unlimited). Note that
                        this does not limit the number of major versions (see
                        also matrix-max-n-major-version). For example, if
                        Python 2 and Python 3 are resolved by the recipe and
                        associated matrix conditions, a total of Nx2 builds
                        will be identified. (default: 2 if no matrix
                        conditions)
```


Example
=======

Supposing we have two moderately complex conda recipes in a directory:

```
$ mkdir -p my_recipes/recipe_a my_recipes/recipe_b
$ cat <<EOF > my_recipes/recipe_a/meta.yaml
package:
  name: recipe_a
  version: 2.4

requirements:
  build:
    - python
  run:
    - python

EOF

$ cat <<EOF > my_recipes/recipe_b/meta.yaml
package:
  name: recipe_b
  version: 3.2

requirements:
  build:
    - recipe_a
    - numpy x.x
  run:
    - recipe_a
    - python
    - numpy x.x

EOF
```

If we wish to build the lot, we can simply run:

```
$ conda-build-all my_recipes

conda-build-all my_recipes
Fetching package metadata: ........
Resolving distributions from 2 recipes... 
Computed that there are 11 distributions from the 2 recipes:
Resolved dependencies, will be built in the following order: 
    recipe_a-2.4-py26_0 (will be built: True)
    recipe_a-2.4-py27_0 (will be built: True)
    recipe_a-2.4-py34_0 (will be built: True)
    recipe_a-2.4-py35_0 (will be built: True)
    recipe_b-3.2-np19py26_0 (will be built: True)
    recipe_b-3.2-np110py27_0 (will be built: True)
    recipe_b-3.2-np19py27_0 (will be built: True)
    recipe_b-3.2-np110py34_0 (will be built: True)
    recipe_b-3.2-np19py34_0 (will be built: True)
    recipe_b-3.2-np110py35_0 (will be built: True)
    recipe_b-3.2-np19py35_0 (will be built: True)

BUILD START: recipe_a-2.4-py26_0
...

```

As you can see, these two unassuming recipes will result in more than 2 builds.
In this case, ``recipe_a`` has been identified to be built against the top two minor versions of the top two major versions of Python - that is, py26, py27, py34, py35 (at the time of writing).
Next, ``recipe_b`` has been identified to be built against the top two minor versions of the top two major versions of Python *and* numpy.
If all built distributions of python and numpy were available, there would be ``4 x 2`` permutations (4 being the number of Python versions available, and 2 being the number of numpy versions, assuming there exists only 1 major version of numpy, otherwise this would double to 4).

We've seen that we can build a *lot* of distributions for our simple recipes. We can tighten the build matrix somewhat by adding or own conditions:

```
$ conda-build-all my_recipes --matrix-condition "python 3.5.*" "numpy >=1.8"
Fetching package metadata: ........
Resolving distributions from 2 recipes... 
Computed that there are 3 distributions from the 2 recipes:
Resolved dependencies, will be built in the following order: 
    recipe_a-2.4-py35_0 (will be built: True)
    recipe_b-3.2-np110py35_0 (will be built: True)
    recipe_b-3.2-np19py35_0 (will be built: True)
...
```

Here we've used the language provided to us by conda to limit the build matrix to a smaller number of combinations. Alternatively we could use the max ``N`` major and minor arguments to limit the scope:

```
$ conda-build-all my_recipes --matrix-max-n-minor-versions=1 --matrix-max-n-major-versions=1
Fetching package metadata: ........
Resolving distributions from 2 recipes... 
Computed that there are 2 distributions from the 2 recipes:
Resolved dependencies, will be built in the following order: 
    recipe_a-2.4-py35_0 (will be built: True)
    recipe_b-3.2-np110py35_0 (will be built: True)
...

```


