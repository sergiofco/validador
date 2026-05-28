# Editor analise_siplan_fluxo — POC

## Como rodar

```
pip install flask flask-cors azure-identity pyodbc
cd poc_editor
python server.py
```

- Browser abre automaticamente em **http://localhost:8080**
- Login com conta SESC (@sescsp.org.br)
- Requer: **ODBC Driver 17 ou 18 for SQL Server**
  - Download: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server

---

## Arquitetura

```
Browser (localhost:8080)
  └── Flask server.py
       ├── Auth: InteractiveBrowserCredential (Azure CLI app, sem App Registration proprio)
       ├── GET /api/whoami  → e-mail do usuario logado
       ├── GET /api/data    → SELECT da tabela via pyodbc
       └── POST /api/update → UPDATE via pyodbc
```

## IDs Fabric (já configurados em server.py)

| | |
|---|---|
| Workspace | `c282684f-8e0a-4b71-a451-ba44a8652a63` (Siplan_GEDES) |
| Warehouse | `8faf35b9-bdf7-4860-8ed2-00ca6a3775c2` (wh_siplan_fluxo) |
| SQL Endpoint | `beu5bmmdbuwedpv62ucm524jzi-j5uifqqkrzyuxjcrxjckqzjkmm.datawarehouse.fabric.microsoft.com` |
| Tabela | `wh_siplan_fluxo.dbo.analise_siplan_fluxo` |

## Estado atual (2026-05-28)

- Autenticação ✅
- Leitura de dados ✅
- Exibição da tabela ✅ (bug CSS corrigido)
- Filtros ✅
- Salvar status ✅ (código pronto)

## Próximos passos

1. Testar salvar status de uma atividade
2. Habilitar edição de `custos_editavel`
3. Decidir hospedagem definitiva (servidor local vs Azure Function)
