<?php
/**
 * Plugin Name: FAFAR Institutional Security
 * Description: Deployment-managed safeguards for the institutional website.
 */
if (!defined('ABSPATH')) exit;
if (!defined('DISALLOW_FILE_EDIT')) define('DISALLOW_FILE_EDIT', true);

// Defense in depth: reject executable content even when given a document filename.
add_filter('wp_handle_upload_prefilter', function ($file) {
    $path = $file['tmp_name'] ?? '';
    if (!is_string($path) || !is_file($path)) return $file;
    $prefix = file_get_contents($path, false, null, 0, 4096);
    if ($prefix === false) {
        $file['error'] = 'Não foi possível verificar o arquivo enviado.';
        return $file;
    }
    $text = ltrim($prefix, "\xef\xbb\xbf \t\r\n");
    if (substr($prefix, 0, 4) === "\x7fELF" || substr($prefix, 0, 2) === 'MZ'
        || substr($text, 0, 2) === '#!' || preg_match('/<\?(?:php\b|=)/i', $prefix)) {
        $file['error'] = 'O arquivo enviado contém código executável.';
    }
    return $file;
});
