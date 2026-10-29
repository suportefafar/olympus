<?php
$fixture=sys_get_temp_dir().'/recovery-'.bin2hex(random_bytes(5)).'/';
mkdir($fixture.'wp-admin/includes',0755,true);file_put_contents($fixture.'wp-admin/includes/plugin.php','<?php');
define('ABSPATH',$fixture);
$filters=[];
$actions=[];
function add_action($name,$callback,...$args) { $GLOBALS['actions'][$name][]=$callback; }
function add_filter($name,$callback) { $GLOBALS['filters'][$name]=$callback; }
require dirname(__DIR__).'/institutional-security.php';
assert(DISALLOW_FILE_EDIT === true);
$check=$filters['wp_handle_upload_prefilter'];
$path=tempnam(sys_get_temp_dir(),'upload-');
try {
 foreach(["\x7fELFbinary","MZbinary","#!/bin/sh\n","<!-- disguise --><?php echo 'test';"] as $body) {
  file_put_contents($path,$body);assert(isset($check(['tmp_name'=>$path])['error']));
 }
 file_put_contents($path,'%PDF-1.7 safe document');assert(!isset($check(['tmp_name'=>$path])['error']));
 echo "PASS: institutional upload safeguards and file editor restriction\n";
} finally { unlink($path); }

$options=[];$password_resets=0;$active=false;
function get_option($key) { return $GLOBALS['options'][$key]??false; }
function add_option($key,$value,...$args) { if(isset($GLOBALS['options'][$key]))return false;$GLOBALS['options'][$key]=$value;return true; }
function update_option($key,$value,...$args) { $GLOBALS['options'][$key]=$value; }
function delete_option($key) { unset($GLOBALS['options'][$key]); }
function get_userdata($id) { return (object)['ID'=>50,'user_login'=>'silviaverdenolasco']; }
function wp_generate_password(...$args) { return str_repeat('unrecorded',8); }
function wp_set_password($password,$id) { $GLOBALS['password_resets']++; }
class WP_Session_Tokens { public static $revocations=0;static function destroy_all_for_all_users() { self::$revocations++; } }
function is_plugin_active($name) { return $GLOBALS['active']; }
function activate_plugin($name) { $GLOBALS['active']=true;return null; }
function is_wp_error($result) { return false; }
try {
 $recover=$actions['wp_loaded'][0];$recover();$recover();
 assert($password_resets===1);assert(WP_Session_Tokens::$revocations===1);assert($active===true);
 $result=get_option('fafar_security_recovery_20261029');
 assert($result['weak_password_invalidated'] && $result['previous_sessions_revoked'] && $result['wordfence_active']);
 echo "PASS: one-time credential/session recovery, Wordfence activation and idempotence\n";
} finally { unlink($fixture.'wp-admin/includes/plugin.php');rmdir($fixture.'wp-admin/includes');rmdir($fixture.'wp-admin');rmdir($fixture); }

define('WFWAF_OPERATIONAL',true);
class wfConfig { static function save($changes) { wfWAF::$mode=$changes['wafStatus']; } }
class wfWAF {
 public static $mode='disabled';
 static function getInstance() { return new self(); }
 function getRules() { return [1,2,3]; }
 function getStorageEngine() { return $this; }
 function getConfig($key) { return self::$mode; }
}
$enable=$actions['wp_loaded'][1];$enable();assert(wfWAF::$mode==='enabled');
assert(get_option('fafar_security_firewall_20261029')['rule_count']===3);
wfWAF::$mode='changed-by-administrator';$enable();assert(wfWAF::$mode==='changed-by-administrator');
echo "PASS: WAF enabled once through Wordfence API, subsequent admin choices preserved\n";
