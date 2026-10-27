# Ambiente de desenvolvimento local

No desenvolvimento, o WordPress (`intranet-website`) usa `http://intranet.farmacia.local` e a nova intranet Rails usa `http://intranet-stage.farmacia.local`. Para iniciar a aplicação e o proxy com as configurações locais, use `./olymctl dev up intranet --no-pull`.

Os arquivos WordPress locais ficam diretamente em `fafar/institutional-website/`, `fafar/intranet-website/` e `fafar/escuta-website-wp/`, ao lado de `olympus/` e `intranet/`. Os serviços `institutional-website`, `intranet-website` e `wordpress-sync` usam `../institutional-website/html` e `../intranet-website/html` nos arquivos Compose. Preserve essas pastas, incluindo uploads e plugins, ao reorganizar os checkouts; elas contêm dados locais e não são preparadas pelo `olymctl`.

Para iniciar o site institucional com MySQL e o proxy, use `olymctl dev up institutional-website` e acesse `http://farmacia.local` (ou `http://www.farmacia.local`). O comando usa o conteúdo existente em `../institutional-website/html`, sem exigir repositório Git ou `.env` nessa pasta. Use `--no-pull` para testar alterações locais do Olympus; `--branch` e `--commit` não se aplicam aos serviços WordPress. `olymctl dev down institutional-website` para somente o site.

O `olymctl dev up` prepara o host para os domínios locais `*.farmacia.local` e inicia os serviços. A inclusão dessas entradas em `/etc/hosts` é responsabilidade do Olympus porque faz parte da preparação do ambiente de desenvolvimento. Se precisar de privilégios administrativos, o comando pede autorização antes de alterar o arquivo. Domínios de produção `*.farmacia.ufmg.br` devem usar DNS normal e nunca ser mapeados para `127.0.0.1`.

O overlay dev publica Dike em `127.0.0.1:3002` e PostgreSQL, MySQL e MongoDB em `127.0.0.1:5432`, `:3306` e `:27017`. Esses ports ficam disponíveis apenas no host de desenvolvimento.

As rotas Caddy e a configuração Compose do proxy estão no [guia de integração do repositório reverse-proxy](https://github.com/suportefafar/reverse-proxy/blob/main/docs/OLYMPUS-INTEGRATION.md).

Para iniciar apenas o Laras com o proxy, use `./olymctl dev up laras2026-website --no-pull`. O site fica em `http://laras2026.farmacia.local`; o Nginx serve diretamente os arquivos do checkout `../laras2026-website`, permitindo visualizar alterações sem reconstruir uma imagem.

A intranet Rails em dev monta o checkout inteiro `../intranet:/rails` (bind mount), incluindo código, configuração, views, assets e storage. O Rails recarrega alterações de código sem rebuild da imagem. As gems continuam em `/usr/local/bundle`, fora desse mount; mudanças de dependências ou da imagem base ainda podem exigir rebuild. SCSS continua sendo compilado no checkout com `npm run build:css`. Não substituir esse mount por apenas `storage/` nem usar rebuild de imagem para publicar mudanças comuns de código no dev.

## Athenas

`olymctl dev up athenas --no-pull` inicia o grupo web, worker, Ollama e os inicializadores de banco/modelo, com acesso em `http://athenas.farmacia.local` e HTTPS pela CA local. `olymctl dev down athenas` para somente esse grupo e preserva os dados; `olymctl dev status` mostra os serviços. O proxy é recarregado após `up` para aplicar alterações nas rotas sem depender da recriação de sua imagem.

O Athenas usa `athenas_development` no `postgres-db` compartilhado, com credenciais de `olympus/.env`. O overlay dev compila `olympus-postgres-pgvector:17` sobre `postgres:17-trixie`, adicionando a extensão e mantendo PostgreSQL 17, a mesma família Debian/glibc e o volume `olympus_postgres-data`; faça backup antes dessa primeira troca. As extensões `vector` e `unaccent` são criadas somente no banco do Athenas. O banco de testes, quando utilizado, é `athenas_test`.

Configure o administrador inicial em `athenas/.env`; o inicializador aplica migrations e seed idempotente antes de liberar web/worker. O inicializador do Ollama baixa o modelo definido nesse arquivo antes de iniciar o worker. Web, worker e inicializador montam o checkout inteiro `../athenas:/rails` por bind mount. Código, configuração, views e assets vêm diretamente do workspace; uploads ficam em `athenas/storage/`, e e-mails capturados em `athenas/tmp/mail/`. O Rails recarrega alterações comuns em desenvolvimento; reinicie o worker após alterar código de jobs. Gems e o perfil do LibreOffice ficam na imagem, fora de `/rails`; mudanças de dependências ainda exigem rebuild. Modelos continuam no volume `athenas_ollama`. Na migração, os volumes antigos `olympus_athenas-storage`/`olympus_athenas-mail` são preservados para recuperação. Não há publicação de portas de Athenas/Ollama no host: o acesso web passa pelo proxy.
