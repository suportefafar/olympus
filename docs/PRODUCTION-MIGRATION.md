# Migração de produção — 2026-10-09

Origem dos apps: `prod.farmacia.ufmg.br:20022`, `/var/services-infra`.
Origem dos bancos: `10.10.10.10`, acessada pelo LXC de apps com as credenciais dos containers originais.
Destino: `150.164.110.1:10022`, VM `services-infra`, IP interno `10.10.10.1`.

## Arquivos no destino

- `/opt/fafar`: repositórios dos apps e Olympus.
- `/var/services-infra`: arquivos originais, uploads WordPress e storage de ChatRapido/StageManager.
- `/var/reverse-proxy/web-server/certs`: certificados reais, montados somente em runtime.
- `/var/backups/olympus-migration`: dumps, checksums, configurações privadas originais e registros da restauração. Acesso restrito a root.
- `/opt/fafar/olympus/compose.prod.local.yaml`: override privado do servidor, carregado automaticamente pelo CLI.
- `/opt/fafar/olympus/production`: configuração institucional e ciphertext de credenciais preservados.

Os backups históricos do plugin WordPress em `wp-content/ai1wm-backups` (aproximadamente 58 GB) permanecem no LXC original. Os arquivos necessários aos sites foram transferidos (aproximadamente 19 GB).

## Bancos

A cópia física fornecida foi feita com bancos ligados; por isso a restauração usa dumps lógicos novos do servidor original. Os apps, workers e autoheal da origem foram parados antes das exportações; suas políticas originais estão preservadas no inventário privado.

- PostgreSQL 17: dump de todos os bancos e roles.
- MySQL 5.7.44: dump completo, incluindo usuários, grants, eventos e rotinas. A versão foi mantida durante a migração; a atualização de major é uma operação separada.
- MongoDB 8.0.13: dump geral mais dump explícito de `local`, utilizado pelo Prometheus Bot.

Os checksums dos dumps recebidos foram conferidos. Antes de iniciar migrações dos apps, PostgreSQL e MySQL apresentaram contagens idênticas às da origem em 684 tabelas (16 bancos PostgreSQL e 10 bancos MySQL).

Duas views já inválidas na origem, `sitefafar.disciplinas` e `sitefafar.reservas`, referenciam a tabela ausente `intranet.reservas`. Suas definições estão salvas em `source/mysql-invalid-views.sql`; não foram inventadas tabelas ou dados para recriá-las.

A VM originalmente expunha CPU QEMU sem AVX. MongoDB 8 exige AVX; o tipo de CPU precisa expor as instruções do processador físico, por exemplo `host` no Proxmox. A alteração exige desligar e iniciar a VM. Após o desligamento/início feito pelo operador, a VM passou a reconhecer Intel Xeon Silver 4416+ com AVX/AVX2 e o MongoDB iniciou normalmente.

## Operação

```sh
cd /opt/fafar/olympus
./olymctl prod up --no-pull
```

O comando conserva o override local. As credenciais reais permanecem nos arquivos privados do servidor; nunca copiar `.env` de desenvolvimento sobre eles. Preservar as chaves Rails e Hermes vinculadas aos dados restaurados.

Para disparar operações de outra máquina, configure usuário e chave SSH localmente para `150.164.110.1`; o `olymctl` já fixa esse IP e a porta `10022`. Deixe `olymctl` disponível no `PATH` da sessão SSH no servidor. O histórico, os builds e as leituras de containers continuam no servidor:

```sh
olymctl prod --remote up
olymctl prod --remote up escuta --no-pull
olymctl prod --remote rollback escuta
olymctl prod --remote status
olymctl prod --remote ports
```

A configuração do proxy publica os serviços de produção do Olympus. Os antigos painéis administrativos, monitor externo e Escuta stage não são publicados por esse arquivo.

## Resultado do deploy

- 17 containers em execução: três bancos, proxy e treze serviços de aplicação.
- MongoDB: `stagemanager.rooms` com 3 documentos e `local.ticketlinkers` com 4.302, iguais à origem. O banco Rails do StageManager contém 14 salas; são dados diferentes do legado MongoDB.
- Escuta usa `escuta_production`, com 207 acolhidos na conferência e versão de consentimento `2025`.
- StageManager usa `stagemanager`, `stagemanager_cache`, `stagemanager_queue` e `stagemanager_cable`. Não substituir esses nomes pelos defaults do template.
- A descriptografia do provedor SMTP Hermes foi verificada sem exibir credenciais ou enviar mensagem de teste. Os workers e agendamentos de produção estão ativos.
- WordPress preserva o usuário `1000:1000` da origem; uploads e Wordfence permanecem graváveis sem alterar permissões gerais dos arquivos.
- Imagens e PDFs Laras, ignorados pelo Git, foram copiados de `/var/services-infra/laras2026-website/{images,docs}` para o checkout antes do build. Os 80 arquivos referenciados responderam HTTP 200. Preservar essas pastas em futuros deploys e backups.
- Prometheus usa `API_INTRANET_BASE_URL=http://intranet-website/wp-json/intranet/v1/`; Têmis usa apenas `http://intranet-website`. Os dois programas esperam formatos diferentes.
- Cronos publica UDP/123 em `10.10.10.1:123` na VM via Compose de produção; a regra DNAT UDP/123 do Proxmox para esse endereço também é necessária para acesso externo. As redes permitidas são `150.164.110.0/24`, `150.164.111.0/24` e `192.168.137.0/24`; a rede Docker edge `172.30.10.0/24` permite comunicação interna. O proxy HTTPS conserva a restrição às redes externas originais.

Foram conferidos certificado TLS, páginas finais e arquivos CSS/JS/imagens dos domínios do proxy. Institucional apresenta o conteúdo existente; intranet, Escuta e Hermes apresentam login; StageManager, ChatRápido (incluindo `c`), Laras e Design System apresentam suas páginas. Dike responde em `/api/health`; a raiz `/` não é uma página da API. Cronos responde HTTP 200 internamente e pacote NTP de 48 bytes em modo servidor; clientes fora das redes autorizadas recebem 403 por HTTPS.

O alias `nova-escuta` redireciona para Escuta. O WordPress legado continua com seu endereço canônico preservado, que redireciona `escuta-wp` para Escuta Rails. Os dados legados foram mantidos; esse alias não constitui um portal WordPress independente.

Registros detalhados ficam em `/var/backups/olympus-migration`: `count-comparison.json`, `http-check.json`, `pages-check.json`, `laras-assets-check.json` e logs de deploy. A origem permanece parada para evitar execução duplicada de jobs; não religar seus apps após a migração.

## Cuidados operacionais restantes

- Renovar e instalar o certificado TLS antes de **18/12/2026**; o proxy usa o certificado importado, sem emissão automática para esses domínios.
- Incluir no backup regular os volumes dos bancos, uploads/storage, imagens/PDFs Laras, certificados e arquivos privados de configuração. Os dumps da migração são um ponto de recuperação, não um agendamento de backups.
- Preservar no LXC antigo os aproximadamente 58 GB de backups históricos WordPress até definir sua retenção.
- As duas views MySQL inválidas descritas acima continuam pendentes de revisão de suas dependências na aplicação legada.

- Configurar uma credencial de leitura Git para os repositórios privados `escuta-website`, `temis` e `prometheus-bot` antes de executar atualizações sem `--no-pull`. O deploy atual usa checkouts locais completos e não depende desse acesso.
- Confirmar UDP/123 a partir de um cliente real das redes permitidas. O protocolo foi validado pela rede Docker; a tentativa pelo IP público a partir do LXC antigo expirou (o acesso HTTPS por esse mesmo caminho também falhou). A publicação da porta na VM está ativa; o encaminhamento externo depende da rede de produção.
