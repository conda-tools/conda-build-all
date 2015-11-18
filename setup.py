from setuptools import setup


setup(
      name='conda-build-all',
      version='0.1.0',
      description='Build all conda recipes within a directory/repository.',
      author='Phil Elson',
      author_email='pelson.pub@gmail.com',
      url='https://github.com/scitools/conda-buildall',
      packages=['conda_build_all'],
      entry_points={
          'console_scripts': [
              'conda-build-all = conda_build_all.cli:main',
              # This is needed as conda can't deal with dashes in subcommands yet
              # (see https://github.com/conda/conda/pull/1840).
              'conda-buildall = conda_build_all.cli:main',
          ]
      },
     )

