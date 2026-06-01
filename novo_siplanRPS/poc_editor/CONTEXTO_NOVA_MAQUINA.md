# Contexto para continuação na nova máquina
**Atualizado em:** 2026-05-31

---

## O que é este projeto

Editor HTML local (Flask + pyodbc) para visualizar e editar campos de `wh_siplan_rps.dbo.analise_siplan_rps` no Fabric Warehouse, sem exigir licença Premium.

```
Browser (http://localhost:8080)
  └── server.py (Flask)
       ├── Auth: InteractiveBrowserCredential() → scope database.windows.net
       ├── GET  /api/whoami → email do usuário logado
       ├── GET  /api/data   → SELECT da tabela (pyodbc)
       └── POST /api/update → UPDATE Status/campos (pyodbc)
```

---

## ⚠️ Mudança importante desde a última sessão

`wh_siplan_fluxo` e `analise_siplan_fluxo` foram **abandonados**.

O projeto usa **exclusivamente**:
- Warehouse: `wh_siplan_rps`
- Tabela: `wh_siplan_rps.dbo.analise_siplan_rps`
- SQL Endpoint: `beu5bmmdbuwedpv62ucm524jzi-dmrv7k3fbwbevh5d4sidg3urfq.datawarehouse.fabric.microsoft.com`

O `server.py` atual ainda aponta para o endpoint antigo. **Primeira coisa a fazer:** corrigir as duas constantes abaixo.

---

## Correção imediata no server.py

```python
# ANTES (errado — warehouse abandonado)
SQL_ENDPOINT = 'beu5bmmdbuwedpv62ucm524jzi-j5uifqqkrzyuxjcrxjckqzjkmm.datawarehouse.fabric.microsoft.com'
TABLE        = 'wh_siplan_fluxo.dbo.analise_siplan_fluxo'

# DEPOIS (correto)
SQL_ENDPOINT = 'beu5bmmdbuwedpv62ucm524jzi-dmrv7k3fbwbevh5d4sidg3urfq.datawarehouse.fabric.microsoft.com'
TABLE        = 'wh_siplan_rps.dbo.analise_siplan_rps'
```

---

## Novos campos em analise_siplan_rps (adicionados 2026-05-31)

| Campo | Tipo | Origem | Para o editor |
|-------|------|--------|---------------|
| `justificativa` | texto longo | `tabela_base` | leitura — `<textarea readonly>` ou painel expansível |
| `todas_as_tags` | texto médio, pipe-sep | `tabela_base` | leitura — chips/badges separando por `\|` |
| `info_pcap` | texto multilinha | tabela `pcap`, agregado | leitura — `<pre>` ou card; múltiplas PCAPs separadas por `\n\n`; cada bloco tem: Proponente / Total R$ / Status / Grupos |
| `mesma_pcap` | CSV de atividade_ids | self-join em `pcap_num` | leitura — lista de links; ao clicar filtra/destaca a linha correspondente na tabela |

### Formato do campo `info_pcap` (para uma PCAP)
```
Proponente: João Silva
Total: R$ 50.000
Status: Aprovada
Grupos: Audiovisual
Sonorização
```

### Formato do campo `info_pcap` (múltiplas PCAPs)
```
[1]
Proponente: João Silva
Total: R$ 50.000
Status: Aprovada
Grupos: Audiovisual

[2]
Proponente: Maria Santos
Total: R$ 30.000
Status: Em análise
Grupos: Produção
```

---

## SELECT recomendado para /api/data

Acrescentar os 4 novos campos ao SELECT existente:

```sql
SELECT
    atividade_id,
    nome,
    unidade,
    gerencia,
    area,
    linguagem,
    mes,
    autonomia,
    CONVERT(VARCHAR(10), dataPrimeiraSessao, 120) AS dataPrimeiraSessao,
    custos_foto,
    custos_editavel,
    justificativa,
    todas_as_tags,
    info_pcap,
    mesma_pcap,
    [Status],
    CONVERT(VARCHAR(16), data_entrega, 120) AS data_entrega,
    quem
FROM wh_siplan_rps.dbo.analise_siplan_rps
ORDER BY data_entrega DESC
```

---

## Schema completo da tabela (campos relevantes)

| Campo | Editável via editor | Observação |
|-------|-------------------|------------|
| `atividade_id` | ❌ | PK |
| `nome` | ❌ | |
| `unidade` | ❌ | |
| `gerencia` | ❌ | |
| `area` | ❌ | |
| `linguagem` | ❌ | |
| `mes` | ❌ | formato "2026-mai" |
| `autonomia` | ❌ | UO / STS / DIREG |
| `dataPrimeiraSessao` | ❌ | |
| `custos_foto` | ❌ | snapshot da entrega, nunca atualizado |
| `custos_editavel` | ✅ | textarea multilinha |
| `justificativa` | ❌ (por ora) | textarea readonly |
| `todas_as_tags` | ❌ | display chips |
| `info_pcap` | ❌ | display pré-formatado |
| `mesma_pcap` | ❌ | display como links |
| `Status` | ✅ | dropdown — ver valores abaixo |
| `data_entrega` | ❌ | |
| `quem` | ❌ | email |
| `observacoes` | ✅ | textarea (se existir) |
| `orientaUO` | ✅ | textarea (se existir) |
| `Modificado` | auto | preenchido no UPDATE pelo server.py |
| `Modificado por` | auto | email do usuário logado |

### Status válidos
```python
STATUSES_PERMITIDOS = {
    'Enviada', 'Reenviada', 'Em revisão', 'AutonomiaUO',
    'Aprovada', 'Não aprovada', 'Em análise',
}
```

---

## IDs Fabric (referência)

| Item | Valor |
|------|-------|
| Workspace | `c282684f-8e0a-4b71-a451-ba44a8652a63` (Siplan_GEDES) |
| Warehouse ativo | `wh_siplan_rps` |
| SQL Endpoint | `beu5bmmdbuwedpv62ucm524jzi-dmrv7k3fbwbevh5d4sidg3urfq.datawarehouse.fabric.microsoft.com` |
| Lakehouse gold | `lake_gold_fatos` (fonte de `base` e `pcap`) |

---

## Como rodar

```bash
pip install flask flask-cors azure-identity pyodbc
cd novo_siplanRPS/poc_editor
python server.py
# browser abre automaticamente em http://localhost:8080
# login com conta SESC (@sescsp.org.br)
```

**Requisito:** ODBC Driver 17 ou 18 for SQL Server instalado.  
Download: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server

---

## Estado em 2026-05-31

| Componente | Estado |
|------------|--------|
| Auth (InteractiveBrowserCredential) | ✅ funcionando |
| `/api/whoami` | ✅ |
| `/api/data` (SELECT) | ✅ — precisa trocar endpoint + adicionar 4 campos |
| Exibição da tabela | ⚠️ bug CSS corrigido (`display:block`), não retestado |
| `/api/update` (UPDATE Status) | ✅ código pronto, testado |
| Exibição dos novos campos | ❌ pendente — implementar no HTML |
| Hospedagem definitiva | ❌ pendente |

---

## Notebooks relacionados (Fabric)

| Notebook | Função |
|----------|--------|
| `nb_fluxo_autorizacao.ipynb` | Grava analise_siplan_rps via PA após Approval — inclui todos os 4 novos campos |
| `nb_carga_massa_analise.ipynb` | Carga em massa dos novos campos (rodar poucas vezes); requer tabela existente; ~15 min para 3.300 registros |
| `nb_AnaliseSiplanRPS.ipynb` | Recria a tabela a partir do staging (Dataflow Gen2) — rodar se a tabela sumir |
