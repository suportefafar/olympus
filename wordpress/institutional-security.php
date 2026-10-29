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

// One-time recovery after the 2026-10-29 incident. A server-side database backup
// was created before this release. Keep the result for an auditable, idempotent run.
add_action('wp_loaded', function () {
    $key = 'fafar_security_recovery_20261029';
    if (get_option($key) || !add_option($key . '_lock', gmdate('c'), '', false)) return;
    $result = ['completed_utc' => gmdate('c')];
    $user = get_userdata(50);
    $result['weak_account_found'] = $user && $user->user_login === 'silviaverdenolasco';
    if ($result['weak_account_found']) {
        // Do not retain or send a replacement password; use WordPress recovery.
        wp_set_password(wp_generate_password(64, true, true), $user->ID);
        $result['weak_password_invalidated'] = true;
    }
    WP_Session_Tokens::destroy_all_for_all_users();
    $result['previous_sessions_revoked'] = true;
    require_once ABSPATH . 'wp-admin/includes/plugin.php';
    if (!is_plugin_active('wordfence/wordfence.php')) {
        $activation = activate_plugin('wordfence/wordfence.php');
        $result['wordfence_activation_error'] = is_wp_error($activation);
    }
    $result['wordfence_active'] = is_plugin_active('wordfence/wordfence.php');
    update_option($key, $result, false);
    delete_option($key . '_lock');
}, 99);

// Plugin activation preserves its old settings. The incident audit found its WAF
// disabled, so enable the installed rule set through Wordfence's own save API.
add_action('wp_loaded', function () {
    $key = 'fafar_security_firewall_20261029';
    if (get_option($key) || !class_exists('wfConfig') || !class_exists('wfWAF')) return;
    $waf = wfWAF::getInstance();
    if (!defined('WFWAF_OPERATIONAL') || !WFWAF_OPERATIONAL || !count($waf->getRules())) return;
    wfConfig::save(['wafStatus' => 'enabled']);
    if ($waf->getStorageEngine()->getConfig('wafStatus') === 'enabled') {
        update_option($key, ['enabled_utc' => gmdate('c'), 'rule_count' => count($waf->getRules())], false);
    }
}, 100);
