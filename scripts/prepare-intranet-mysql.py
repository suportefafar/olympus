#!/usr/bin/env python3
"""Provision the intranet reader through the legacy MySQL local socket."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess


def source_settings(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('WP_SYNC_') and '=' in line:
            key, value = line.split('=', 1)
            values[key] = value.strip().strip('\"\'')
    return values


def statements(values):
    database = values.get('WP_SYNC_MYSQL_DATABASE', '')
    reader = values.get('WP_SYNC_MYSQL_USERNAME', '')
    prefix = values.get('WP_SYNC_TABLE_PREFIX', 'wp_')
    password = values.get('WP_SYNC_MYSQL_PASSWORD', '')
    if database != 'intranet_wp' or reader != 'intranet_rails_sync':
        raise ValueError('Refusing an unexpected production source database or reader')
    if not re.fullmatch(r'[a-zA-Z0-9_]{1,64}', prefix):
        raise ValueError('Invalid WordPress table prefix')
    if not re.fullmatch(r'[0-9a-fA-F]{48,128}', password):
        raise ValueError('The dedicated reader password must be generated hexadecimal data')
    tables = [prefix + suffix for suffix in ['users', 'usermeta', 'fafar_cf7crud_submissions']]
    account = f"'{reader}'@'%'"
    probe = "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = '" + database + "' AND ENGINE = 'InnoDB' AND TABLE_NAME IN (" + ','.join(f"'{t}'" for t in tables) + ');'
    commands = [f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY '{password}';", f"ALTER USER {account} IDENTIFIED BY '{password}';"]
    commands += [f'GRANT SELECT ON `{database}`.`{table}` TO {account};' for table in tables]
    return probe, '\n'.join(commands), f'SHOW GRANTS FOR {account};'



def reservation_statements(values):
    statements(values)  # Reuse the production database/account/prefix validation.
    database = values['WP_SYNC_MYSQL_DATABASE']
    prefix = values.get('WP_SYNC_TABLE_PREFIX', 'wp_')
    if len(prefix + 'intranet_ticket_number_sequence') > 64:
        raise ValueError('WordPress prefix is too long for the reservation table')
    deploy = Path(__file__).resolve().parents[2] / 'intranet' / 'deploy'
    schema = (deploy / 'wordpress-ticket-number-schema.sql').read_text().replace('__PREFIX__', prefix)
    trigger = (deploy / 'wordpress-ticket-number-trigger.sql').read_text().replace('__PREFIX__', prefix)
    password = hashlib.sha256(('intranet-ticket-number-writer:' + values['WP_SYNC_MYSQL_PASSWORD']).encode()).hexdigest()
    account = "'intranet_rails_numbers'@'%'"
    grants = f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY '{password}';\nALTER USER {account} IDENTIFIED BY '{password}';\n"
    grants += f"GRANT SELECT, INSERT ON `{database}`.`{prefix}fafar_cf7crud_submissions` TO {account};\n"
    grants += f"GRANT SELECT, UPDATE ON `{database}`.`{prefix}intranet_ticket_number_sequence` TO {account};"
    probe = f"SELECT ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = '{database}' AND TRIGGER_NAME = '{prefix}intranet_ticket_number_insert';"
    return f"USE `{database}`;\n" + schema, f"USE `{database}`;\n" + trigger, grants, f"SHOW GRANTS FOR {account};", probe


def mysql(container, sql):
    command = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --protocol=socket --user=root --batch --raw --skip-column-names'
    result = subprocess.run(['docker', 'exec', '-i', container, 'sh', '-c', command], input=sql, text=True, capture_output=True)
    if result.returncode:
        # Driver output may include supplied SQL; never print it or credentials.
        raise RuntimeError('The local MySQL socket operation failed')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--env-file', required=True)
    args = parser.parse_args()
    try:
        values = source_settings(args.env_file)
        probe, grants, verification = statements(values)
        if mysql(args.container, probe) != '3':
            raise RuntimeError('The three WordPress source tables must exist and use InnoDB')
        mysql(args.container, grants)
        output = mysql(args.container, verification)
        allowed = {f'GRANT SELECT ON `intranet_wp`.`{values.get("WP_SYNC_TABLE_PREFIX", "wp_")}{suffix}`' for suffix in ['users', 'usermeta', 'fafar_cf7crud_submissions']}
        for line in output.splitlines():
            if not line.startswith('GRANT USAGE ON *.* ') and not any(line.startswith(prefix + ' TO ') for prefix in allowed):
                raise RuntimeError('The dedicated reader has unexpected privileges')
        schema, trigger, writer_grants, writer_verification, trigger_probe = reservation_statements(values)
        mysql(args.container, schema)
        existing_trigger = mysql(args.container, trigger_probe)
        expected_body = trigger.split('BEGIN', 1)[1].rsplit('END$$', 1)[0]
        if not existing_trigger:
            mysql(args.container, trigger)
        elif re.sub(r'\s+', ' ', existing_trigger).strip() != re.sub(r'\s+', ' ', 'BEGIN' + expected_body + 'END').strip():
            raise RuntimeError('The ticket-number trigger differs from the reviewed version')
        # Include rows inserted before the trigger acquired its DDL lock.
        mysql(args.container, schema)
        mysql(args.container, writer_grants)
        writer_output = mysql(args.container, writer_verification)
        writer_allowed = {
            f"GRANT SELECT, INSERT ON `intranet_wp`.`{values.get('WP_SYNC_TABLE_PREFIX', 'wp_')}fafar_cf7crud_submissions`",
            f"GRANT SELECT, UPDATE ON `intranet_wp`.`{values.get('WP_SYNC_TABLE_PREFIX', 'wp_')}intranet_ticket_number_sequence`",
        }
        for line in writer_output.splitlines():
            if not line.startswith('GRANT USAGE ON *.* ') and not any(line.startswith(prefix + ' TO ') for prefix in writer_allowed):
                raise RuntimeError('The ticket-number writer has unexpected privileges')
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'[ERROR] {error}\n')
    print('[INFO] Verified the read-only WordPress reader and isolated ticket-number writer/counter.')


if __name__ == '__main__':
    main()
