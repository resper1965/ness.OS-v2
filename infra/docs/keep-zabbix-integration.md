# Integração Zabbix ➔ Keep AIOps

Este documento detalha como configurar o Zabbix para enviar alertas brutos para a API do Keep, permitindo que o Keep assuma o papel de agrupamento, deduplicação e higienização (substituindo o antigo webhook que apontava direto para a API Python `n.infraops`).

## Pré-requisitos
- Keep AIOps em execução (via `app/docker-compose.keep.yml`).
- Uma **API Key** gerada na interface do Keep (Settings > API Keys).
- A URL externa ou interna do Keep acessível pelo servidor Zabbix (ex: `http://ninf-keep-backend:8080` ou `https://keep.ness.com.br`).

---

## Passo 1: Criar o Provider Zabbix no Keep
1. Acesse o dashboard do Keep (`http://localhost:3000`).
2. Vá em **Providers** e procure por **Zabbix**.
3. Siga o fluxo para gerar a URL de Webhook específica que o Keep vai escutar para este provider. O Keep irá fornecer uma URL como: `https://<keep-url>/api/alerts/event/zabbix?api_key=<SUA_API_KEY>`.

---

## Passo 2: Configurar Media Type no Zabbix
1. No Zabbix, navegue para **Alerts** > **Media types**.
2. Clique em **Create media type**.
3. Defina os seguintes campos:
   - **Name:** Keep AIOps Webhook
   - **Type:** Webhook
   - **Parameters:** Crie um payload JSON robusto contendo o que o Keep precisa para as regras de agrupamento:
     - `alert_name` ➔ `{EVENT.NAME}`
     - `severity` ➔ `{EVENT.SEVERITY}`
     - `host_name` ➔ `{HOST.NAME}`
     - `host_ip` ➔ `{HOST.IP}`
     - `event_id` ➔ `{EVENT.ID}`
     - `status` ➔ `{EVENT.STATUS}`
     - `cluster_id` ➔ `{HOST.HOSTGROUP.NAMES}` (para agrupar por cliente/cluster)
   - **Script:**
     Cole o seguinte código em JavaScript que faz o POST HTTP para o Keep:

     ```javascript
     try {
         var params = JSON.parse(value),
             req = new HttpRequest(),
             response;
             
         // Substitua pela URL e API Key do Passo 1
         var keep_url = "http://ninf-keep-backend:8080/api/alerts/event/zabbix?api_key=SUA_API_KEY_AQUI";
         
         req.addHeader('Content-Type: application/json');
         Zabbix.log(4, '[ Keep Webhook ] Payload: ' + value);
         
         response = req.post(keep_url, value);
         Zabbix.log(4, '[ Keep Webhook ] Response: ' + response);
         
         return 'OK';
     } catch (error) {
         Zabbix.log(3, '[ Keep Webhook ] Falha ao enviar: ' + error);
         throw 'Falha no Webhook do Keep: ' + error;
     }
     ```

---

## Passo 3: Configurar Trigger Action
1. No Zabbix, navegue para **Alerts** > **Actions** > **Trigger actions**.
2. Crie uma nova Action chamada `Escalonamento para Keep AIOps`.
3. Em **Conditions**, defina quais alertas você deseja mandar. Exemplo: `Severity is greater than or equals Warning`.
4. Em **Operations**, adicione uma operação enviando a mensagem para o grupo de usuários `Zabbix administrators` (ou o usuário que você atrelou à media type) através do Media Type **Keep AIOps Webhook**.
5. Em **Recovery operations**, faça o mesmo para notificar o Keep que o problema foi resolvido (o Keep fechará o incidente nativamente se receber `status = RESOLVED`).

---
Com isso, a inteligência de processamento de alertas sai do Zabbix e passa integralmente para o **Keep**.
