<?php
/**
 * Plugin Name: WordPress Authenticated Backup Downloads
 * Description: Allows administrators to download All-in-One WP Migration exports.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_action( 'template_redirect', 'intranet_backup_download', PHP_INT_MIN );

function intranet_backup_download() {
	if ( ! isset( $_GET['intranet_protected_backup'] ) ) {
		return;
	}

	nocache_headers();
	if ( ! is_user_logged_in() ) {
		auth_redirect();
		exit;
	}
	if ( ! current_user_can( 'manage_options' ) ) {
		status_header( 403 );
		exit;
	}
	if ( ! in_array( $_SERVER['REQUEST_METHOD'], array( 'GET', 'HEAD' ), true ) ) {
		status_header( 405 );
		header( 'Allow: GET, HEAD' );
		exit;
	}

	$name = $_GET['intranet_protected_backup'];
	if ( ! is_string( $name ) || ! preg_match( '/\A[a-zA-Z0-9][a-zA-Z0-9._-]*\.wpress\z/', $name ) ) {
		status_header( 404 );
		exit;
	}
	$base = realpath( WP_CONTENT_DIR . '/ai1wm-backups' );
	$file = realpath( WP_CONTENT_DIR . '/ai1wm-backups/' . $name );
	if ( false === $base || false === $file || dirname( $file ) !== $base || ! is_file( $file ) || ! is_readable( $file ) ) {
		status_header( 404 );
		exit;
	}

	$handle = fopen( $file, 'rb' );
	if ( false === $handle ) {
		status_header( 404 );
		exit;
	}
	$size  = fstat( $handle )['size'];
	$start = 0;
	$end   = $size - 1;
	$range = isset( $_SERVER['HTTP_RANGE'] ) ? $_SERVER['HTTP_RANGE'] : null;
	if ( null !== $range ) {
		if ( ! preg_match( '/\Abytes=(\d*)-(\d*)\z/', $range, $matches ) || ( '' === $matches[1] && '' === $matches[2] ) ) {
			intranet_backup_range_error( $size );
		}
		if ( '' === $matches[1] ) {
			$length = min( (int) $matches[2], $size );
			if ( $length < 1 ) {
				intranet_backup_range_error( $size );
			}
			$start = $size - $length;
		} else {
			$start = (int) $matches[1];
			if ( '' !== $matches[2] ) {
				$end = min( (int) $matches[2], $end );
			}
		}
		if ( $start > $end || $start >= $size ) {
			intranet_backup_range_error( $size );
		}
		status_header( 206 );
		header( "Content-Range: bytes $start-$end/$size" );
	} else {
		status_header( 200 );
	}

	while ( ob_get_level() ) {
		ob_end_clean();
	}
	// PHP compression would invalidate Content-Length and byte ranges.
	ini_set( 'zlib.output_compression', '0' );
	header( 'X-Content-Type-Options: nosniff' );
	header( 'Content-Type: application/octet-stream' );
	header( 'Content-Disposition: attachment; filename="' . $name . '"' );
	header( 'Accept-Ranges: bytes' );
	header( 'Content-Length: ' . ( $end - $start + 1 ) );
	if ( 'HEAD' === $_SERVER['REQUEST_METHOD'] ) {
		fclose( $handle );
		exit;
	}
	set_time_limit( 0 );
	fseek( $handle, $start );
	$remaining = $end - $start + 1;
	while ( $remaining > 0 && ! feof( $handle ) && ! connection_aborted() ) {
		$chunk = fread( $handle, min( 1048576, $remaining ) );
		if ( false === $chunk || '' === $chunk ) {
			break;
		}
		echo $chunk;
		$remaining -= strlen( $chunk );
		flush();
	}
	fclose( $handle );
	exit;
}

function intranet_backup_range_error( $size ) {
	status_header( 416 );
	header( 'Content-Range: bytes */' . $size );
	exit;
}
