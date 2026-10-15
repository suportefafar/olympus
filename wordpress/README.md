# Downloads de exportações da intranet

O hardening existente bloqueia `wp-content/ai1wm-backups` inclusive quando o
All-in-One WP Migration gera um link de download para um administrador.
O serviço de produção instala uma regra específica antes desse bloqueio para
encaminhar somente arquivos `.wpress` ao WordPress. O MU plugin exige uma sessão
válida e a capacidade `manage_options`, valida o caminho real e suporta GET,
HEAD e um intervalo de bytes, sem carregar o backup inteiro em memória.

O script de inicialização preserva as demais regras de `.htaccess` e recusa
iniciar se o bloco esperado estiver ausente. Não altera proprietários, backups,
banco de dados ou permissões gerais. A pasta e os demais arquivos continuam
bloqueados. Após restaurar um backup antigo, reinicie pelo fluxo de deploy para
reaplicar a regra caso o `.htaccess` tenha sido substituído.

Após commit e push deste repositório, implante com:

```sh
olymctl prod --remote up reverse-proxy
```

O proxy já depende de `intranet-website` no Compose de produção; o comando
recria o WordPress quando sua configuração muda, sem atualizar os outros apps.
O override privado do servidor e os arquivos persistentes WordPress permanecem
preservados.
