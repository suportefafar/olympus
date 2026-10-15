<?php
// Run before Apache. Change only the existing hardening block; keep WP rules.
$path = '/var/www/html/.htaccess';
$old  = file_exists( $path ) ? file_get_contents( $path ) : '';
$deny = 'RewriteRule ^wp-content/ai1wm-backups(?:/|$) - [F,L,NC]';
$rules = 'RewriteRule ^wp-content/ai1wm-backups/([a-zA-Z0-9][a-zA-Z0-9._-]*\.wpress)$ index.php?intranet_protected_backup=$1 [B,END,NC,QSA]' . "\n" . $deny;

// Replace only our own rules on repeated starts, then insert immediately before
// the catch-all deny. Never open backup directory listings or arbitrary files.
$clean = preg_replace( '/^RewriteRule .*intranet_protected_backup=.*\R?/m', '', $old );
if ( false === $clean || substr_count( $clean, $deny ) !== 1 ) {
	fwrite( STDERR, "Expected Intranet Protected Uploads backup rule missing; refusing to start.\n" );
	exit( 1 );
}
$new = str_replace( $deny, $rules, $clean );
if ( $old !== $new && file_put_contents( $path, $new, LOCK_EX ) !== strlen( $new ) ) {
	fwrite( STDERR, "Cannot update the authenticated backup download rule.\n" );
	exit( 1 );
}
