"""Unit test for treadmill.ad.gmsa.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

import ldap3
import mock
import yaml

from treadmill import utils
from treadmill.ad import gmsa
from treadmill.ad import _servers as servers


class HostGroupWatchTest(unittest.TestCase):
    """Mock test for treadmill.ad.gmsa.HostGroupWatch.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.placement_dir = os.path.join(self.root, 'placement')
        self.servers_dir = os.path.join(self.root, 'servers')
        os.mkdir(self.placement_dir)
        os.mkdir(self.servers_dir)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa.HostGroupWatch._check_ldap3_operation',
                mock.Mock())
    def test_sync(self, connection):
        """Test gmsa.HostGroupWatch.sync."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)
        utils.touch(os.path.join(server1_path, 'proid1.app#0000000000001'))

        server2_path = os.path.join(self.placement_dir, 'server2.ad.com')
        os.mkdir(server2_path)
        utils.touch(os.path.join(server2_path, 'proid4.app#0000000000004'))

        server3_path = os.path.join(self.placement_dir, 'server3.ad.com')
        os.mkdir(server3_path)

        server4_path = os.path.join(self.placement_dir, 'server4.ad.com')
        os.mkdir(server4_path)
        utils.touch(os.path.join(server4_path, 'proid3.app#0000000000003'))

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        with io.open(os.path.join(self.servers_dir, 'server2.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server2,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        with io.open(os.path.join(self.servers_dir, 'server3.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server3,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': ['proid1-gmsa-hosts'],
                'member': ['CN=server1,DC=AD,DC=COM']
            }},
            {'attributes': {
                'samAccountName': ['proid2-gmsa-hosts'],
                'member': ['CN=server3,DC=AD,DC=COM']
            }},
            {'attributes': {
                'samAccountName': ['proid3-gmsa-hosts'],
                'member': []
            }},
            {'attributes': {
                'samAccountName': ['proid4-gmsa-hosts'],
                'member': []
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': set(['CN=server1,DC=AD,DC=COM']),
            'proid2': set([]),
            'proid3': set([]),
            'proid4': set(['CN=server2,DC=AD,DC=COM']),
        })

        mock_connection.modify.assert_has_calls([
            mock.call('CN=proid2-gmsa-hosts,OU=test,DC=ad,DC=com',
                      {'member': [(ldap3.MODIFY_DELETE,
                                   ['CN=server3,DC=AD,DC=COM'])]}),
            mock.call('CN=proid4-gmsa-hosts,OU=test,DC=ad,DC=com',
                      {'member': [(ldap3.MODIFY_ADD,
                                   ['CN=server2,DC=AD,DC=COM'])]}),
        ])

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa.HostGroupWatch._check_ldap3_operation',
                mock.Mock())
    def test_on_created_placement(self, connection):
        """Test gmsa.HostGroupWatch._on_created_placement."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': ['proid1-gmsa-hosts'],
                'member': []
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': set([]),
        })

        placement_path = os.path.join(server1_path, 'proid1.app#0000000000001')
        utils.touch(placement_path)
        watch._on_created_placement(placement_path)

        self.assertEqual(watch._proids, {
            'proid1': set(['CN=server1,DC=AD,DC=COM']),
        })

        mock_connection.modify.assert_has_calls([
            mock.call('CN=proid1-gmsa-hosts,OU=test,DC=ad,DC=com',
                      {'member': [(ldap3.MODIFY_ADD,
                                   ['CN=server1,DC=AD,DC=COM'])]}),
        ])

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa.HostGroupWatch._check_ldap3_operation',
                mock.Mock())
    def test_on_deleted_placement(self, connection):
        """Test gmsa.HostGroupWatch._on_deleted_placement."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)
        placement_path = os.path.join(server1_path, 'proid1.app#0000000000001')
        utils.touch(placement_path)

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': ['proid1-gmsa-hosts'],
                'member': []
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': set(['CN=server1,DC=AD,DC=COM']),
        })

        os.remove(placement_path)
        watch._on_deleted_placement(placement_path)

        self.assertEqual(watch._proids, {
            'proid1': set([]),
        })

        mock_connection.modify.assert_has_calls([
            mock.call('CN=proid1-gmsa-hosts,OU=test,DC=ad,DC=com',
                      {'member': [(ldap3.MODIFY_DELETE,
                                   ['CN=server1,DC=AD,DC=COM'])]}),
        ])


if __name__ == '__main__':
    unittest.main()
