# Ambiente de desenvolvimento local

O `olymctl dev up` prepara o host para os domínios locais `*.farmacia.local` e inicia os serviços. A inclusão dessas entradas em `/etc/hosts` é responsabilidade do Olympus porque faz parte da preparação do ambiente de desenvolvimento. Se precisar de privilégios administrativos, o comando pede autorização antes de alterar o arquivo. Domínios de produção `*.farmacia.ufmg.br` devem usar DNS normal e nunca ser mapeados para `127.0.0.1`.

O overlay dev publica Dike em `127.0.0.1:3002` e PostgreSQL, MySQL e MongoDB em `127.0.0.1:5432`, `:3306` e `:27017`. Esses ports ficam disponíveis apenas no host de desenvolvimento.

As rotas Caddy e a configuração Compose do proxy estão no [guia de integração do repositório reverse-proxy](https://github.com/suportefafar/reverse-proxy/blob/main/docs/OLYMPUS-INTEGRATION.md).
