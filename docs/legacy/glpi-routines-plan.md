# Plan: GLPI Automations and Routines Implementation

Implement standard ITIL automations, SLA rules, GMUD approval workflows, and cron tasks in GLPI to support the `infraops`, `secops`, and `devarch` teams.

---

## Confirmed Specifications

1. **Change Approvers (GMUD validation)**:
   * `TI > Gestão de Mudanças (GMUD) > GMUD - Infraestrutura` ➔ Approval requested from: **`iaraujo`** (ID 7)
   * `TI > Gestão de Mudanças (GMUD) > GMUD - Segurança` ➔ Approval requested from: **`agsilva`** (ID 21)
   * `TI > Gestão de Mudanças (GMUD) > GMUD - Sistemas` ➔ Approval requested from: **`bertuzzi`** (ID 57)
2. **Support Email (Mailgate)**:
   * Active receiver to be created: **`helpdesk@ness.com.br`** (IMAP placeholder config)
3. **Market Standard SLA Targets**:
   * **Muito Alta (Critical)** ➔ Response: **15 min** | Resolution: **2h** (SLA T1)
   * **Alta (High)** ➔ Response: **1h** | Resolution: **4h** (SLA T2)
   * **Média (Medium)** ➔ Response: **4h** | Resolution: **12h** (SLA T3)
   * **Baixa (Low)** ➔ Response: **8h** | Resolution: **48h** (SLA T4)
4. **Auto-Close Solved Tickets**:
   * Automatic closing duration: **3 days** (72 hours)

---

## Tasks

- [ ] Task 1: Create GLPI Business Rules (Regras de Negócio) to automatically route categories to their technical groups:
  * Categories under `TI > Acessos e Identidades > Rede e VPN`, `E-mail` and `Infraestrutura` ➔ Group **`infraops`** (ID 13)
  * Categories under `TI > Segurança da Informação` and `GMUD - Segurança` ➔ Group **`secops`** (ID 6)
  * Categories under `TI > Sistemas e Aplicações` and `GMUD - Sistemas` ➔ Group **`devarch`** (ID 14)
  ➔ Verify: Run test insertions and verify `groups_id` matches.

- [ ] Task 2: Configure automatic Approval Requests (Pedidos de Validação) for all tickets under `TI > Gestão de Mudanças (GMUD)` targeting the resolved group leads:
  * `GMUD - Infraestrutura` ➔ Approver: user ID 7 (`iaraujo`)
  * `GMUD - Segurança` ➔ Approver: user ID 21 (`agsilva`)
  * `GMUD - Sistemas` ➔ Approver: user ID 57 (`bertuzzi`)
  ➔ Verify: Check `glpi_rules` database entries for validation requests.

- [ ] Task 3: Create SLA definitions in database table `glpi_slas` and trigger escalation rules based on ticket urgency:
  * Urgency 5 (Muito Alta) ➔ SLA T1 (2h resolution)
  * Urgency 4 (Alta) ➔ SLA T2 (4h resolution)
  * Urgency 3 (Média) ➔ SLA T3 (12h resolution)
  * Urgency 2 or 1 (Baixa) ➔ SLA T4 (48h resolution)
  ➔ Verify: Verify `glpi_slas` is populated with correct target times.

- [ ] Task 4: Configure the automatic closing routine (`closeticket` task) in `glpi_crontasks` to 3 days (259200 seconds):
  * Set `delay` = 3 days in `glpi_configs` for `autoclose_delay` or `closeticket` task settings.
  ➔ Verify: Query `glpi_configs` or `glpi_crontasks` to confirm.

- [ ] Task 5: Configure the Mailgate IMAP receiver for `helpdesk@ness.com.br` in `glpi_mailcollectors`:
  * Create entry for `helpdesk@ness.com.br` with placeholder host `imap.ness.com.br`, SSL enabled, port 993.
  ➔ Verify: Verify mail collector exists in `glpi_mailcollectors`.

- [ ] Task 6: Ensure LDAP/Authentik user synchronization cron task (`ldap` action) and mail receiver task (`mailgate`) are set to "CLI" mode and configured in crontab:
  * Ensure GLPI crontab `/etc/cron.d/glpi` executes `php bin/console cron:run` every minute.
  ➔ Verify: Query `glpi_crontasks` to verify run mode for `mailgate` and `ldap` is set to 2 (CLI).

---

## Done When
- [ ] Group assignment rules are active.
- [ ] Auto-validation rules for GMUD are active and mapped to ismael, agnaldo, and bertuzzi.
- [ ] SLA targets are configured in the database.
- [ ] Autoclose delay is set to 3 days.
- [ ] Mailgate collector is created.
- [ ] Crontab is configured for CLI execution of background tasks.
