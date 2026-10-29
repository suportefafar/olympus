<?php
// Deployment-managed configuration, applied before Apache accepts requests.
$path = '/var/www/html/.htaccess';
$old = is_file($path) ? file_get_contents($path) : '';
if ($old === false) throw new RuntimeException('Cannot read WordPress rewrite configuration.');
$begin = '# BEGIN FAFAR Institutional Security';
$end = '# END FAFAR Institutional Security';
$clean = preg_replace('/^# BEGIN FAFAR Institutional Security\R.*?^# END FAFAR Institutional Security\R?/ms', '', $old);
if ($clean === null || strpos($clean, $begin) !== false || strpos($clean, $end) !== false) throw new RuntimeException('Malformed institutional security block.');
$rules = <<<'RULES'
# BEGIN FAFAR Institutional Security
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule (^|/)\.(git|svn|hg)(/|$) - [F,L,NC]
RewriteRule (^|/)\.env([./]|$) - [F,L,NC]
RewriteRule ^wp-config\.php([.~_-].*|$) - [F,L,NC]
RewriteRule ^wp-content/ai1wm-backups/([a-zA-Z0-9][a-zA-Z0-9._-]*\.wpress)$ index.php?intranet_protected_backup=$1 [B,END,NC,QSA]
RewriteRule ^wp-content/ai1wm-backups(/|$) - [F,L,NC]
</IfModule>
# END FAFAR Institutional Security
RULES;
$new = $rules . "\n" . $clean;
if ($new !== $old && file_put_contents($path, $new, LOCK_EX) !== strlen($new)) throw new RuntimeException('Cannot apply institutional security rules.');
