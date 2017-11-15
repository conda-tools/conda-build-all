from argparse import Namespace
from contextlib import contextmanager
import logging
try:
    from unittest import mock
except ImportError:
    import mock
import os
import shutil
import sys
import tempfile
import unittest


from conda_build_all.tests.unit.dummy_index import DummyIndex, DummyPackage
from conda_build_all.artefact_destination import (ArtefactDestination,
                                                  AnacondaClientChannelDest,
                                                  DirectoryDestination)
import conda_build_all.artefact_destination


class Test_AnacondaClientChannelDest(unittest.TestCase):
    # These tests make extensive use of mock to avoid the need to contact the
    # conda.anaconda.org server.
    # Integration tests which do use the server are available for inspect_binstar.
    def setUp(self):
        self.logger_patch = mock.patch('conda_build_all.artefact_destination.log')
        self.logger = self.logger_patch.start()

    def tearDown(self):
        self.logger_patch.stop()

    def _get_config(self):
        # Provide an object that will behave like a conda_build config object.
        config = mock.Mock()
        config.bldpkgs_dir = mock.Mock(return_value='')
        return config

    @contextmanager
    def dist_exists_setup(self, on_owner, on_channel):
        dist_exists = mock.patch('conda_build_all.inspect_binstar.distribution_exists', return_value=on_owner)
        dist_exists_on_channel = mock.patch('conda_build_all.inspect_binstar.distribution_exists_on_channel', return_value=on_channel)
        with dist_exists:
            with dist_exists_on_channel:
                yield

    def test_not_already_available_not_just_built(self):
        client, owner, channel = [mock.sentinel.client, mock.sentinel.owner,
                                  mock.sentinel.channel]
        ad = AnacondaClientChannelDest(mock.sentinel.token, owner, channel)
        ad._cli = client
        meta = DummyPackage('a', '2.1.0')
        config = self._get_config()
        with self.dist_exists_setup(on_owner=True, on_channel=False):
            with mock.patch('conda_build_all.inspect_binstar.add_distribution_to_channel') as add_to_channel:
                ad.make_available(meta, mock.sentinel.dist_path,
                                  just_built=False, config=config)
        add_to_channel.assert_called_once_with(client, owner, meta, channel=channel)
        self.logger.info.assert_called_once_with('Adding existing a-0.0-0 to the sentinel.owner/sentinel.channel channel.')

    def test_not_already_available_just_built(self):
        client, owner, channel = [mock.sentinel.client, mock.sentinel.owner,
                                  mock.sentinel.channel]
        ad = AnacondaClientChannelDest(mock.sentinel.token, owner, channel)
        ad._cli = client
        meta = DummyPackage('a', '2.1.0')
        config = self._get_config()
        with self.dist_exists_setup(on_owner=False, on_channel=False):
            with mock.patch('conda_build_all.build.upload') as upload:
                ad.make_available(meta, mock.sentinel.dist_path,
                                  just_built=True, config=config)
        upload.assert_called_once_with(client, meta, owner,
                                       channels=[channel], config=config)
        self.logger.info.assert_called_once_with('Uploading a to the sentinel.channel channel.')

    def test_already_available_not_just_built(self):
        # Note, we exercise the use of get_binstar here too.

        client, owner, channel = [mock.sentinel.client, mock.sentinel.owner,
                                  mock.sentinel.channel]
        ad = AnacondaClientChannelDest(mock.sentinel.token, owner, channel)
        meta = DummyPackage('a', '2.1.0')
        config = self._get_config()
        with self.dist_exists_setup(on_owner=True, on_channel=True):
            with mock.patch('binstar_client.utils.get_binstar') as get_binstar:
                ad.make_available(meta, mock.sentinel.dist_path,
                                  just_built=False, config=config)
        get_binstar.assert_called_once_with(Namespace(site=None, token=mock.sentinel.token))
        # Nothing happens, we just get a message.
        self.logger.info.assert_called_once_with('Nothing to be done for a - it is already on sentinel.owner/sentinel.channel.')

    def test_already_available_just_built(self):
        client, owner, channel = [mock.sentinel.client, mock.sentinel.owner,
                                  mock.sentinel.channel]
        ad = AnacondaClientChannelDest(mock.sentinel.token, owner, channel)
        ad._cli = client
        meta = DummyPackage('a', '2.1.0')
        config = self._get_config()
        with self.dist_exists_setup(on_owner=True, on_channel=True):
            ad.make_available(meta, mock.sentinel.dist_path,
                              just_built=True, config=config)
        # Nothing happens, we just get a message.
        self.logger.warn.assert_called_once_with("Assuming the distribution we've just built and the one on sentinel.owner/sentinel.channel are the same.")

    def test_already_available_elsewhere(self):
        client, owner, channel = [mock.sentinel.client, mock.sentinel.owner,
                                  mock.sentinel.channel]
        ad = AnacondaClientChannelDest(mock.sentinel.token, owner, channel)
        ad._cli = client
        meta = DummyPackage('a', '2.1.0')
        config = self._get_config()
        source_owner = 'fake_owner'
        # The osx-64 subdirectory at the end of the URL is not important to the test.
        for url in ['http://foo.bar/{}/osx-64/'.format(source_owner),
                    'https://foo.bar/wibble/{}/osx-64/'.format(source_owner),
                    'https://foo.bar/wibble/{}/osx-64'.format(source_owner)]:
            with self.dist_exists_setup(on_owner=False, on_channel=False):
                with mock.patch('conda_build_all.inspect_binstar.copy_distribution_to_owner') as copy:
                    ad.make_available(meta, url, just_built=False,
                                      config=config)
            copy.assert_called_once_with(ad._cli, source_owner, owner, meta, channel=channel)

    def test_from_spec_owner(self):
        spec = 'testing'
        os.environ['BINSTAR_TOKEN'] = 'a test token'
        dest = AnacondaClientChannelDest.from_spec(spec)
        self.assertEqual(dest.token, 'a test token')
        self.assertEqual(dest.owner, 'testing')
        self.assertEqual(dest.channel, 'main')

    def test_from_spec_owner_and_channel(self):
        spec = 'testing_owner/channels/my_channel'
        os.environ['BINSTAR_TOKEN'] = 'a test token'
        dest = AnacondaClientChannelDest.from_spec(spec)
        self.assertEqual(dest.token, 'a test token')
        self.assertEqual(dest.owner, 'testing_owner')
        self.assertEqual(dest.channel, 'my_channel')


class Test_DirectoryDestination(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='recipes')
        self.dd = DirectoryDestination(self.tmp_dir)
        self.dummy_meta = mock.sentinel.dummy_meta
        self.dummy_path1 = mock.sentinel.dummy_path1
        self.dummy_path2 = mock.sentinel.dummy_path2

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_not_copying(self):
        with mock.patch('shutil.copy') as copy:
            self.dd.make_available(self.dummy_meta,
                                   self.dummy_path1,
                                   just_built=False)
        self.assertEqual(copy.call_count, 0)

    def test_copying(self):
        with mock.patch('shutil.copy') as copy:
            self.dd.make_available(self.dummy_meta,
                                   self.dummy_path1,
                                   just_built=True)
        copy.assert_called_once_with(self.dummy_path1, self.tmp_dir)

    def test_copying_multi(self):
        paths = (self.dummy_path1, self.dummy_path2)
        with mock.patch('shutil.copy') as copy:
            self.dd.make_available(self.dummy_meta,
                                   paths,
                                   just_built=True)
        calls = [mock.call(path, self.tmp_dir) for path in paths]
        copy.assert_has_calls(calls)


if __name__ == '__main__':
    unittest.main()
