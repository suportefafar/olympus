import pathlib
import runpy
import unittest

statements = runpy.run_path(str(pathlib.Path(__file__).with_name('prepare-intranet-mysql.py')))['statements']


class ReaderProvisioningTest(unittest.TestCase):
    def values(self):
        return {'WP_SYNC_MYSQL_DATABASE': 'intranet_wp', 'WP_SYNC_MYSQL_USERNAME': 'intranet_rails_sync', 'WP_SYNC_MYSQL_PASSWORD': 'a' * 48, 'WP_SYNC_TABLE_PREFIX': 'wp_'}

    def test_grants_are_limited_to_the_three_read_only_source_tables(self):
        probe, commands, verify = statements(self.values())
        self.assertIn("ENGINE = 'InnoDB'", probe)
        grants = [line for line in commands.splitlines() if line.startswith('GRANT ')]
        self.assertEqual(len(grants), 3)
        self.assertTrue(all(line.startswith('GRANT SELECT ON `intranet_wp`.`wp_') for line in grants))
        self.assertNotIn('ALL PRIVILEGES', commands)
        self.assertNotIn('DROP ', commands)
        self.assertNotIn('DELETE ', commands)
        self.assertEqual(verify, "SHOW GRANTS FOR 'intranet_rails_sync'@'%';")

    def test_existing_application_users_and_other_databases_are_refused(self):
        for key, value in [('WP_SYNC_MYSQL_USERNAME', 'root'), ('WP_SYNC_MYSQL_DATABASE', 'sitefafar')]:
            with self.assertRaises(ValueError):
                statements(dict(self.values(), **{key: value}))

    def test_sql_metacharacters_in_prefix_or_password_are_refused(self):
        for key in ['WP_SYNC_TABLE_PREFIX', 'WP_SYNC_MYSQL_PASSWORD']:
            with self.assertRaises(ValueError):
                statements(dict(self.values(), **{key: "x'; DROP DATABASE intranet_wp;--"}))


if __name__ == '__main__':
    unittest.main()
