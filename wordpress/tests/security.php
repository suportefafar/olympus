<?php
define('ABSPATH',__DIR__);
$filters=[];
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
