import argparse
import conda_build_all
#import conda_build_all.builder


def main():
    parser = argparse.ArgumentParser(description='Build many conda distributions.')

    parser.add_argument('--version', action='version', version=conda_build_all.__version__)

    parser.add_argument('recipes',
                        help='The folder containing conda recipes to build.')
    parser.add_argument('--inspect-channel', nargs='*',
                        help=('Skip a build if the equivalent disribution is already '
                              'available in the specified channel.'))
    parser.add_argument('--inspect-directory', nargs='*',
                        help='Skip a build if the equivalent disribution is already available in the specified directory.')
    parser.add_argument('--upload-channel', nargs='*',
                        help=('The channel(s) to upload built distributions to. It is '
                              'rare to specify this without the --inspect-channel argument. '
                              'If a file:// channel, the build will be copied to the directory. '
                              'If a url:// channel, the build will be uploaded with the anaconda '
                              'client functionality.'))

    parser.add_argument("--matrix-conditions", nargs='*', default=[],
                        help="Extra conditions for computing the build matrix.")
    parser.add_argument("--matrix-max-n-major-versions", default=2,
                        help=("When computing the build matrix, limit to the latest n major versions "
                              "(0 makes this unlimited). For example, if Python 1, 2 and Python 3 are "
                              "resolved by the recipe and associated matrix conditions, only the latest N major "
                              "version will be used for the build matrix. (default: 2)"))
    parser.add_argument("--matrix-max-n-minor-versions", default=2,
                        help=("When computing the build matrix, limit to the latest n minor versions "
                              "(0 makes this unlimited). Note that this does not limit the number of major "
                              "versions (see also matrix-max-n-major-version). For example, if Python 2 and "
                              "Python 3 are resolved by the recipe and associated matrix conditions, a total "
                              "of Nx2 builds will be identified. "
                              "(default: 2)"))


    args = parser.parse_args()

    print(args)
    b = conda_build_all.builder.Builder(args.recipes, 'pelson', 'main')
    b.extra_build_conditions = args.matrix_conditions
    b.main()
    raise NotImplementedError("The functionality doesn't exist yet.")
