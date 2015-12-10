import argparse
import logging
import os

import conda_build.config

import conda_build_all
import conda_build_all.builder
import conda_build_all.artefact_destination as artefact_dest


def main():
    parser = argparse.ArgumentParser(
                              description='Build many conda distributions.')

    parser.add_argument('--version', action='version',
                        version=conda_build_all.__version__,
                        help="Show conda-build-all's version, and exit.")

    parser.add_argument('recipes',
        help='The folder containing conda recipes to build.')
    parser.add_argument('--inspect-channels', nargs='*',
        help=('Skip a build if the equivalent disribution is already '
              'available in the specified channel.'))
    parser.add_argument('--inspect-directories', nargs='*',
        help=('Skip a build if the equivalent disribution is already '
              'available in the specified directory.'))
    parser.add_argument('--no-inspect-conda-bld-directory', default=False,
        action='store_true',
        help='Do not add the conda-build directory to the inspection list.')

    parser.add_argument('--artefact-directory',
        help='A directory for any newly built distributions to be placed.')
    parser.add_argument('--upload-channels', nargs='*', default=[],
        help=('The channel(s) to upload built distributions to (requires '
              'BINSTAR_TOKEN envioronment variable).'))

    parser.add_argument("--matrix-conditions", nargs='*', default=[],
        help=("Extra conditions for computing the build matrix "
              "(e.g. 'python 2.7.*'). Note, your build matrix may also be being "
              "limited by --matrix-max-n-major-versions and "
              "--matrix-max-n-minor-versions."))
    parser.add_argument("--matrix-max-n-major-versions", default=2, type=int,
        help=("When computing the build matrix, limit to the latest n major "
              "versions (0 makes this unlimited). For example, if Python 1, "
              "2 and Python 3 are resolved by the recipe and associated "
              "matrix conditions, only the latest N major version will be "
              "used for the build matrix. (default: 2) "))
    parser.add_argument("--matrix-max-n-minor-versions", default=2, type=int,
        help=("When computing the build matrix, limit to the latest n minor "
              "versions (0 makes this unlimited). Note that this does not "
              "limit the number of major versions (see also "
              "matrix-max-n-major-version). For example, if Python 2 and "
              "Python 3 are resolved by the recipe and associated matrix "
              "conditions, a total of Nx2 builds will be identified. "
              "(default: 2)"))

    args = parser.parse_args()

    matrix_conditions = args.matrix_conditions
    max_n_versions = (args.matrix_max_n_major_versions,
                      args.matrix_max_n_minor_versions)

    inspection_directories = args.inspect_directories or []
    print(args)
    if (not args.no_inspect_conda_bld_directory and
            os.path.isdir(conda_build.config.config.bldpkgs_dir)):
        inspection_directories.append(conda_build.config.config.bldpkgs_dir)

    artefact_destinations = []
    for channel in args.upload_channels:
        dest = artefact_dest.AnacondaClientChannelDest.from_spec(channel)
        artefact_destinations.append(dest)
    if args.artefact_directory:
        dest = artefact_dest.DirectoryDestination(args.artefact_directory)
        artefact_destinations.append(dest)

    artefact_dest.log.setLevel(logging.INFO)
    artefact_dest.log.addHandler(logging.StreamHandler())

    b = conda_build_all.builder.Builder(args.recipes, args.inspect_channels,
                                        inspection_directories,
                                        artefact_destinations,
                                        args.matrix_conditions,
                                        max_n_versions)
    b.main()


if __name__ == '__main__':
    main()
