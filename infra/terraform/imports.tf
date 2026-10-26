import {
  for_each = { zabbix_prod = "203409070", aiops = "203409271", zabbix_uat = "203532557" }
  to       = contabo_instance.vps[each.key]
  id       = each.value
}

import {
  to = contabo_object_storage.data_storage
  id = "5cf116ec-254f-4f22-9fa4-4d4d2350b067"
}
