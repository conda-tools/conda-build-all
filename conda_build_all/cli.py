import argparse
import logging

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
    parser.add_argument('--no-inspect-conda-bld-directory', default=True,
        action='store_false',
        help='Do not add the conda-build directory to the inspection list.')

    parser.add_argument('--artefact-directory',
        help='A directory for any newly built distributions to be placed.')
    parser.add_argument('--upload-channels', nargs='*', default=[],
        help=('The channel(s) to upload built distributions to (requires '
              'BINSTAR_TOKEN envioronment variable).'))

    parser.add_argument("--matrix-conditions", nargs='*', default=[],
        help=("Extra conditions for computing the build matrix "
              "(e.g. 'python 2.7.*'). "
              "When set, the defaults for matrix-max-n-major-versions and "
              "matrix-max-n-minor-versions are set to 0 (i.e. no limit on "
              "the max n versions)."))
    parser.add_argument("--matrix-max-n-major-versions", default=-1, type=int,
        help=("When computing the build matrix, limit to the latest n major "
              "versions (0 makes this unlimited). For example, if Python 1, "
              "2 and Python 3 are resolved by the recipe and associated "
              "matrix conditions, only the latest N major version will be "
              "used for the build matrix. (default: 2 if no matrix "
              "conditions)"))
    parser.add_argument("--matrix-max-n-minor-versions", default=-1, type=int,
        help=("When computing the build matrix, limit to the latest n minor "
              "versions (0 makes this unlimited). Note that this does not "
              "limit the number of major versions (see also "
              "matrix-max-n-major-version). For example, if Python 2 and "
              "Python 3 are resolved by the recipe and associated matrix "
              "conditions, a total of Nx2 builds will be identified. "
              "(default: 2 if no matrix conditions)"))

    args = parser.parse_args()

    matrix_conditions = args.matrix_conditions
    max_n_versions = (args.matrix_max_n_major_versions,
                      args.matrix_max_n_minor_versions)
    if not matrix_conditions:
        default_n_versions = 2
    else:
        # Unlimited.
        default_n_versions = 0
    if -1 in max_n_versions:
        max_n_versions = tuple(n if n != -1 else default_n_versions
                               for n in max_n_versions)

    inspection_directories = args.inspect_directories or []
    if (not args.no_inspect_conda_bld_directory and
            os.path.isdir(conda_build.config.bldpkgs_dir)):
        inspection_directories.append(conda_build.config.bldpkgs_dir)

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
