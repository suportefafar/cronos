# Cronos — referência para agentes e administração

Cronos é o serviço local de horário dos laboratórios. Ele oferece dois meios de acesso:

1. **NTP/SNTP em UDP/123**, para sincronizar o relógio do sistema operacional. Prefira este meio para computadores.
2. **API HTTP em HTTPS**, para consultar horário e fuso em automações que precisem desses dados. A API não substitui um cliente NTP para acertar o relógio com precisão.

Este documento orienta agentes de IA que serão solicitados a configurar computadores clientes. O agente deve primeiro identificar o sistema operacional, o serviço de sincronização já instalado e as políticas locais, e então configurar o cliente existente de forma idempotente.

## Endereços e acesso

| Uso | Endereço | Transporte |
| --- | --- | --- |
| API de horário em produção | `https://cronos.farmacia.ufmg.br/time` | HTTPS, TCP/443 via Caddy |
| API de horário em desenvolvimento | `https://cronos.farmacia.local/time` | HTTPS, TCP/443 via Caddy com CA interna |
| NTP/SNTP | `cronos.farmacia.ufmg.br` ou o IP interno fixo do servidor | UDP/123 diretamente no host |

A API também responde em `/` e `/api/time`. O serviço NTP não passa pelo Caddy: o Compose publica UDP/123 diretamente no host. O firewall deve permitir UDP/123 e HTTPS apenas para as redes autorizadas.

O filtro padrão aceita origens em `150.164.110.0/24`, `150.164.111.0/24` e `192.168.137.0/24`. Os gateways dos laboratórios fazem SNAT; portanto, Cronos normalmente vê o endereço do gateway nas duas redes `150.164.*`, e não os IPs privados dos PCs atrás dele. A rede `192.168.137.0/24` também está autorizada para clientes cujo endereço de origem chegue diretamente ao serviço sem SNAT. Se o roteamento ou NAT mudar, revise `ALLOWED_NETWORKS`, a regra do Caddy e o firewall.

O Cronos registra no log do container as requisições NTP recebidas e rejeitadas, com endereço de origem e motivo (`source_not_allowed`, `packet_too_short` ou `unsupported_version_or_mode`). Na API HTTP, o Caddy registra todas as respostas no access log do proxy, incluindo os `403` da regra de rede; as respostas `403` e `404` geradas pela aplicação aparecem no log do container Cronos.

### DNS e independência externa

Os clientes podem usar `cronos.farmacia.ufmg.br` se o DNS institucional resolver o nome para o endereço alcançável dentro da rede. Para que uma falha de DNS não impeça a sincronização, configure o cliente NTP com o **IP interno fixo do host Cronos**, após confirmar qual IP é roteável a partir de cada laboratório. Não presuma que `150.164.110.111` seja o IP do serviço: esse endereço foi citado como exemplo de gateway.

Não use um endereço público ou o IP do proxy externo se ele não encaminhar UDP/123. A API HTTPS depende de DNS e de um relógio suficientemente correto para validar o certificado; NTP via IP evita essa dependência de DNS.

## Regras para agentes de IA

- Prefira configurar o cliente NTP nativo do sistema com o host/IP Cronos. Use a API HTTP para consultar campos ou configurar o fuso, não como substituta de NTP para ajuste preciso do relógio.
- NTP sincroniza o instante UTC. Ele **não** altera o timezone do computador. A política de fuso deve ser definida separadamente; para os laboratórios em Minas Gerais, confirme a política local antes de aplicar `America/Sao_Paulo`.
- Preserve o serviço de horário já usado pelo sistema. Configure `systemd-timesyncd`, Chrony, Windows Time ou o cliente existente; evite instalar um segundo daemon concorrente.
- Em computadores Windows associados a um domínio, verifique GPO e hierarquia do domínio antes de substituir a fonte. Em geral, configure o controlador de domínio para usar Cronos e mantenha os clientes na hierarquia do domínio.
- Não desative verificações TLS para consultar a API e não use `date -s`, `Set-Date` ou equivalentes com um valor copiado da resposta HTTP como rotina de sincronização.
- Faça alterações idempotentes: detecte a configuração atual, edite apenas o necessário, reinicie/recarregue o serviço correto e valide a fonte ativa. Registre qualquer política corporativa que impeça a mudança.
- Se DNS puder falhar, use o IP interno fixo aprovado na configuração NTP. Se o IP mudar, atualize os clientes por gerenciamento centralizado.

## Configuração manual dos computadores

Use `cronos.farmacia.ufmg.br` se o DNS institucional interno resolver para o endereço alcançável do servidor. Para não depender de DNS, substitua esse nome pelo IP interno fixo do host Cronos aprovado para a rede do computador. Não use o IP do gateway como se fosse o IP do servidor, a menos que o NTP esteja realmente publicado nele.

As alterações abaixo exigem conta administrativa. Em qualquer sistema, configure apenas um cliente de horário ativo. Se a máquina for gerenciada por domínio, MDM, GPO ou ferramenta institucional, confirme a política antes de mudar a fonte: uma política central pode sobrescrever a configuração local.

### Windows 7

1. Entre com uma conta Administrador.
2. Abra **Painel de Controle → Relógio, Idioma e Região → Data e Hora → Horário na Internet → Alterar configurações**. Marque a sincronização pela Internet e informe `cronos.farmacia.ufmg.br` (ou o IP interno fixo). Se a aba ou os controles estiverem desabilitados, a máquina pode ser gerenciada por domínio/política; use o administrador responsável.
3. Para configurar pela linha de comando, abra **Prompt de Comando como Administrador** e execute:

```bat
w32tm /config /manualpeerlist:"cronos.farmacia.ufmg.br,0x8" /syncfromflags:manual /update
net stop w32time
net start w32time
w32tm /resync /rediscover
w32tm /query /source
w32tm /query /status
```

O sinalizador `0x8` usa o modo cliente NTP. Para independência de DNS, troque o hostname pelo IP interno fixo. Para uma máquina associada a domínio, não force `manual`; mantenha a hierarquia do domínio e configure o controlador de domínio apropriado para usar Cronos.

### Windows 10

1. Abra **Configurações → Hora e idioma → Data e hora**. Ative **Definir hora automaticamente** e confirme o fuso horário conforme a política do laboratório.
2. A interface do Windows pode não permitir escolher um servidor NTP personalizado. Para isso, abra **Prompt de Comando como Administrador** ou **PowerShell como Administrador** e execute:

```bat
w32tm /config /manualpeerlist:"cronos.farmacia.ufmg.br,0x8" /syncfromflags:manual /update
net stop w32time
net start w32time
w32tm /resync /rediscover
w32tm /query /source
w32tm /query /status
```

Use o IP interno fixo no lugar do hostname se a sincronização tiver que continuar durante uma falha de DNS. Em computador associado a domínio, verifique GPO e use `DOMHIER`/hierarquia de domínio conforme a política local em vez de substituir a fonte diretamente.

### Windows 11

1. Abra **Configurações → Hora e idioma → Data e hora**. Ative **Definir hora automaticamente**. Confira o fuso configurado; a sincronização NTP não o altera.
2. Para usar Cronos como fonte manual, abra **Terminal (Admin)**, **Prompt de Comando como Administrador** ou **PowerShell como Administrador** e execute:

```bat
w32tm /config /manualpeerlist:"cronos.farmacia.ufmg.br,0x8" /syncfromflags:manual /update
net stop w32time
net start w32time
w32tm /resync /rediscover
w32tm /query /source
w32tm /query /status
```

Substitua o nome pelo IP interno fixo quando necessário para não depender de DNS. Em máquinas de domínio, não aplique a fonte manual sem autorização do administrador do domínio: o padrão é usar a hierarquia do domínio.

Os comandos `w32tm` são os mesmos nas três versões. A configuração pode ser sobrescrita por política de domínio ou pela organização; `w32tm /query /configuration` ajuda a identificar a configuração efetiva.

### Linux em geral

Linux tem diferentes distribuições e clientes. Primeiro identifique qual está instalado e ativo; não habilite `systemd-timesyncd` junto com Chrony ou `ntpd`:

```sh
timedatectl status
systemctl is-active systemd-timesyncd chrony chronyd ntp ntpd 2>/dev/null
```

Configure somente o cliente ativo, usando **uma** das opções seguintes.

#### systemd-timesyncd

Em distribuições que usam `systemd-timesyncd`, crie `/etc/systemd/timesyncd.conf.d/cronos.conf` como administrador:

```ini
[Time]
NTP=cronos.farmacia.ufmg.br
FallbackNTP=
```

Comandos para criar o arquivo e aplicar a configuração:

```sh
sudo install -d /etc/systemd/timesyncd.conf.d
sudo tee /etc/systemd/timesyncd.conf.d/cronos.conf >/dev/null <<'EOF'
[Time]
NTP=cronos.farmacia.ufmg.br
FallbackNTP=
EOF
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd
sudo timedatectl timesync-status
```

Se a rede não puder depender do DNS, substitua o hostname pelo IP interno fixo. Algumas distribuições não instalam ou não usam `systemd-timesyncd`; nesse caso, use o cliente já instalado.

#### Chrony

Em distribuições que usam Chrony, edite a configuração ativa, normalmente `/etc/chrony/chrony.conf` ou `/etc/chrony.conf`. Inclua:

```conf
server cronos.farmacia.ufmg.br iburst prefer
makestep 1.0 3
```

Se Cronos deve ser a única fonte, remova ou comente as fontes `pool`/`server` externas existentes. Preserve as demais diretivas da distribuição. `makestep 1.0 3` autoriza um ajuste imediato acima de um segundo nas três primeiras atualizações depois de iniciar o daemon; confirme que essa política é adequada ao computador.

Aplique e verifique:

```sh
sudo systemctl restart chrony
chronyc sources -v
chronyc tracking
```

O nome da unidade pode ser `chronyd`. Em `server`, também pode ser usado o IP interno fixo no lugar do nome.

#### ntpd (cliente legado)

Se o computador já usa `ntpd`, edite `/etc/ntp.conf` e adicione uma linha, sem duplicar outras fontes que não devam ser usadas:

```conf
server cronos.farmacia.ufmg.br iburst
```

Reinicie a unidade existente (`ntp` ou `ntpd`, conforme a distribuição) e verifique com `ntpq -pn`. Não instale `ntpd` apenas para seguir este exemplo se a distribuição já usa Chrony ou `systemd-timesyncd`.

### macOS em geral

#### Interface gráfica

- **macOS Ventura e posteriores:** abra **Ajustes do Sistema → Geral → Data e Hora**. Ative o ajuste automático, clique em **Definir** ao lado do servidor de horário e informe `cronos.farmacia.ufmg.br` ou o IP interno fixo.
- **Versões anteriores:** abra **Preferências do Sistema → Data e Hora → Data e Hora**. Ative a configuração automática e informe o servidor de rede Cronos.
- Defina o fuso horário separadamente em **Geral → Data e Hora** (ou na seção **Fuso Horário** das versões antigas), conforme a política do laboratório.

#### Terminal

Em versões com `systemsetup`, um administrador também pode configurar o servidor e ativar a sincronização:

```sh
sudo systemsetup -setnetworktimeserver cronos.farmacia.ufmg.br
sudo systemsetup -setusingnetworktime on
systemsetup -getnetworktimeserver
systemsetup -getusingnetworktime
```

Troque o hostname pelo IP interno fixo se o cliente não puder depender de DNS. Se uma versão do macOS ou um perfil de gerenciamento bloquear esses comandos, use Ajustes do Sistema ou a ferramenta institucional de gerenciamento; não desative a política para forçar a alteração.

## Configuração do timezone

Defina o fuso segundo a política do laboratório; não o derive do deslocamento UTC atual, pois o offset isolado não identifica regras de timezone. A API retorna um nome IANA no campo `timezone`, mas o agente deve confirmar se os PCs devem copiar o fuso do servidor.

Exemplo Linux, somente após confirmar a política:

```sh
sudo timedatectl set-timezone America/Sao_Paulo
```

No Windows, o timezone é uma configuração separada (por exemplo, com `tzutil /s "E. South America Standard Time"`). A conversão entre nomes IANA e nomes Windows deve ser validada para a versão do sistema.

## API HTTP

Exemplo de consulta:

```sh
curl --fail --show-error --silent https://cronos.farmacia.ufmg.br/time
```

Resposta ilustrativa:

```json
{
  "timestamp": "2026-10-07T15:04:05.123Z",
  "unix_time": 1791385445.123,
  "timezone": "America/Sao_Paulo",
  "local_time": "2026-10-07T12:04:05.123-03:00",
  "utc_offset": "-0300"
}
```

| Campo | Significado |
| --- | --- |
| `timestamp` | Instante UTC em formato RFC 3339, com precisão de milissegundos. |
| `unix_time` | Segundos desde a época Unix, em UTC. |
| `timezone` | Nome IANA do timezone configurado no servidor, quando disponível. |
| `local_time` | Horário local do servidor com offset explícito. |
| `utc_offset` | Offset do horário local em relação a UTC (`±HHMM`). |

A API informa a hora observada pelo processo no host. Não aceita comandos para mudar o relógio ou o timezone do cliente. Consultar o endpoint por HTTPS depende de DNS e da validação TLS; para boot com RTC muito incorreto, prefira o cliente NTP nativo.

## Diagnóstico

1. Confirme que o endereço de origem visto pelo serviço está em `150.164.110.0/24`, `150.164.111.0/24` ou `192.168.137.0/24`. Atrás de um gateway com SNAT, normalmente será o IP do gateway nas redes `150.164.*`.
2. Confirme que o nome resolve para o IP interno correto. Para contornar DNS, configure o IP interno fixo do Cronos no cliente.
3. Confirme que o firewall permite tráfego de saída do cliente para UDP/123 e o retorno correspondente; para a API, permita HTTPS/TCP 443.
4. Verifique que UDP/123 está livre no host Cronos. Se o host roda Chrony como cliente de uma fonte externa, o daemon pode também tentar escutar UDP/123 e conflitar com o container. Uma configuração Chrony de host pode usar `port 0` para não abrir o servidor NTP local, mantendo sua função de cliente; confirme isso com a administração do host antes de alterar.
5. Verifique a fonte ativa no cliente (`chronyc sources -v`, `timedatectl timesync-status`, `w32tm /query /source` ou `systemsetup -getnetworktimeserver`). Um serviço ativo não garante que já sincronizou.
6. Lembre que Cronos serve o relógio do host. Se o host estiver incorreto ou não tiver uma fonte confiável, os clientes também receberão uma hora incorreta. Sem upstream, o host pode manter o horário em holdover, mas o desvio cresce com o tempo.

## Operação do serviço

A definição comum está em `compose.yaml`; os comandos de desenvolvimento e produção combinam esse arquivo com seus overlays. Para iniciar em desenvolvimento:

```sh
docker compose --env-file .env -f compose.yaml -f compose.dev.yaml up -d --build cronos reverse-proxy
```

Para iniciar em produção:

```sh
docker compose --env-file .env -f compose.yaml -f compose.prod.yaml up -d --build cronos reverse-proxy
```

Em desenvolvimento, o Compose monta `reverse-proxy/Caddyfile`, que contém somente endereços `.local`; nele, `cronos.farmacia.local` usa certificado emitido pela CA interna do Caddy. Configure DNS local ou o arquivo hosts dos computadores para apontar esse nome ao host de desenvolvimento e instale/confie na CA interna. Em produção, o Compose usa `reverse-proxy/web-server/Caddyfile`, com o hostname `cronos.farmacia.ufmg.br` e certificado que cobre `*.farmacia.ufmg.br`. O serviço Cronos está no `compose.yaml` comum, herdado pelos overlays de dev e prod.

Use `.local` somente para acessar a API HTTP de desenvolvimento. Para NTP, prefira o IP interno fixo ou um nome DNS institucional; `.local` pode ser tratado como mDNS pelos sistemas operacionais.

O Compose define `TZ` como `America/Sao_Paulo` por padrão e aceita `CRONOS_ALLOWED_NETWORKS` para ajustar as redes permitidas. O serviço não sincroniza o host com fontes externas; a administração do servidor deve manter o relógio do host correto e monitorado.

## Referências técnicas

- [Microsoft: Windows Time Service Tools and Settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings) — `w32tm`, fontes manuais, consulta de configuração e estado; documentação atual de Windows 10/11.
- [Microsoft: W32tm (documentação anterior)](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-R2-and-2012/ff799054%28v%3Dws.11%29) — inclui comandos e exemplos aplicáveis a clientes Windows antigos, como Windows 7.
- [Microsoft: resolução de problemas de sincronização](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/time-synchronization-not-succeed-non-ntp) — modo cliente `0x8` e reinício do serviço Windows Time.
- [Apple: configurar data e hora automaticamente no Mac](https://support.apple.com/guide/mac-help/mchlp2996/mac) — servidor de horário de rede pela interface do macOS.
- [Chrony: arquivo de configuração](https://chrony-project.org/doc/4.7/chrony.conf.html) — diretivas `server`, `iburst` e `makestep`.
- [systemd-timesyncd.conf(5)](https://www.freedesktop.org/software/systemd/man/latest/timesyncd.conf.html) — configuração `NTP=` e `FallbackNTP=` do timesyncd.
