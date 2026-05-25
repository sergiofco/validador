# Memória do Projeto — nb_gold_siplan / validador
> Exportado em 2026-05-24 para uso em outra máquina.
> Copie este arquivo para: ~/.claude/projects/<slug-do-projeto>/memory/
> e renomeie cada seção de volta aos arquivos individuais, OU importe como contexto inicial.

---


<!-- ===== MEMORY.md ===== -->

- [RLS implementation](project_rls.md) — design completo do RLS no Fabric para SESC-SP: fontes, regras, DAX, problemas resolvidos
- [Fabric environment](project_fabric_env.md) — detalhes do ambiente Fabric: endpoints, lakehouses, autenticação, lista de notebooks
- [Fabric notebook format](feedback_fabric_notebook_format.md) — metadata obrigatória para importar .ipynb no Fabric sem erro 400; inclui script de correção
- [nb_MatrizPompeia estado](project_matriz_pompeia.md) — notebook de matriz por gerência/área prog: o que faz, fluxo, estado em 2026-05-10, próximos passos
- [Fluxo de autorização SiplanRPS](project_fluxo_autorizacao.md) — design completo do fluxo PA→Approval→nb_fluxo_autorizacao; regras INSERT/UPDATE, mapeamento de campos, parâmetros PA
- [nb_EntregaProgs fluxo validado](project_entrega_progs_flow.md) — arquitetura PA→notebook→OneLake→e-mail; armadilhas; formato TXT/HTML completo: blocos por autonomia, alertas por ação, complemento solicitação
- [Métricas custo/sessão e per capita](project_metricas_custo_sessao.md) — campos canônicos em tabela_base, DAX correto (AMBOS lados filtram capacidade_confiavel), tabelas hist_ para histogramas, relacionamentos no modelo semântico
- [Diagnóstico campos de público](project_diagnostico_publico.md) — resultados D1-D4 + implementação concluída: compute_capacidade(), campos removidos de contracts/solicitacoes, hist_custo e hist_apresentacao criados
- [status_do_fluxo tabela](project_status_do_fluxo.md) — bug fix (lia lakehouse em vez do warehouse) + campos dias_para_inicio e faixa_prazo adicionados; arquitetura final com saveAsTable
- [Padrões Spark↔Fabric](feedback_fabric_write_patterns.md) — o que funciona e o que falha: JDBC leitura/escrita, saveAsTable com dbo, tipos incompatíveis, Direct Lake vs views


<!-- ===== project_metricas_custo_sessao.md ===== -->

---
name: project_metricas_custo_sessao
description: "Regras de negócio e implementação de custo/sessão, custo/hora e per_capita em nb_gold_siplan — inclui campos canônicos em tabela_base, DAX correto, tabelas hist_ e modelo semântico"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4f895958-7b70-4347-a211-c27bb09c0bc9
---

# Métricas de custo por sessão, por hora e per capita

## Regra fundamental (média de razões vs. razão de somas)
Nunca pré-calcular razões em colunas que serão re-agregadas. `por_sessao = custo/sessoes`
por linha produz "média de razões" ao agregar por serviço — valores incorretos.
Correto: `SUM(numerador) / SUM(denominador)` no DAX.

**Why:** Pré-cálculo foi o bug original em `build_contracts` e `build_solicitacoes`.

---

## Implementação (2026-05-23/24) — nb_gold_siplan.ipynb

### Campos removidos
De `build_contracts` e `build_solicitacoes`:
- Parâmetros: `raw_acoes_df`, `datas_df` (não usados após refatoração)
- Campos: `publico_sessao`, `capacidade`, `estimativa`, `tipo_per_capita`, `publico`
- Razões: `por_sessao`, `por_hora`, `per_capita`, `por_sessaoC`, `por_horaC`, `per_capitaC`, `por_hora_valido`, `por_hora_validoC`
- `save_gold(contracts_df, ...)` removido (tabela `contratos` descontinuada no BI)

### Novos campos canônicos em `tabela_base` (via `compute_capacidade()`)
Célula 53 de nb_gold_siplan.ipynb. Grain: atividade_id.

| Campo | Origem | Semântica |
|---|---|---|
| `capacidade_sessao` | `a.lugares` numérico | Lotação do espaço por sessão; NaN se não cadastrado |
| `estimativa_sessao` | `a.estimativa_publico` numérico | Estimativa de público por sessão; NaN se não cadastrado |
| `tipo_per_capita` | regra por serviço | 0 = público acumula por sessão; 1 = público é total (Curso, Seminário) |
| `capacidade_total` | derivado | `capacidade_sessao × qt_sessoes` (tipo=0) ou `capacidade_sessao` (tipo=1); cap 4000 anti-inflação |
| `estimativa_total` | derivado | mesma lógica com `estimativa_sessao` |
| `capacidade_confiavel` | flag | False quando ambos nulos/zero OU atividade tem sessão em local aberto |

Campos antigos `estimativa_publico` e `lugares` removidos do col_order de `tabela_base`.

### Critério `capacidade_confiavel = False`
- Ambos `capacidade_sessao` e `estimativa_sessao` nulos/zero
- OU atividade tem ≥1 sessão em local aberto: regex `praça|convivência|externo|fora|parque|jardim|calçada|pátio|varanda|átrio|hall|foyer|lobby` em `localNome`/`TipologiaLocal`, ou `TipoLocal == 'externa'`
- Locais SEMIFIXOS (ginásio, quadra) NÃO tornam False — variância de capacidade é esperada

---

## Medidas DAX corretas (modelo semântico Direct Lake)

```dax
Custo por Sessão =
DIVIDE(SUM(base[custo_total]), SUM(base[qt_sessoes]))

Per Capita =
DIVIDE(
    CALCULATE(SUM(base[custo_total]),      base[capacidade_confiavel] = TRUE()),
    CALCULATE(SUM(base[capacidade_total]), base[capacidade_confiavel] = TRUE())
)

Custo por Hora =
DIVIDE(
    CALCULATE(SUM(base[custo_total]),  base[servico] IN {"Curso","Oficina","Vivência","Seminário","Mediação","Visita Mediada","Intervenção urbana"}),
    CALCULATE(SUM(base[qt_horas]),     base[servico] IN {"Curso","Oficina","Vivência","Seminário","Mediação","Visita Mediada","Intervenção urbana"})
)
```

Atenção: no Per Capita, **ambos** numerador e denominador devem filtrar `capacidade_confiavel = TRUE()`.
Filtrar só o denominador infla o per_capita incluindo custo de atividades sem capacidade confiável.

---

## Colunas faixa_* em tabela_base (abordagem preferida para histogramas)

`add_faixas_base()` (cell 57 de nb_gold_siplan.ipynb) adiciona três colunas físicas a `tabela_base`:

| Coluna | Cálculo | Quando preenchida |
|---|---|---|
| `faixa_custo_sessao` | `custo_total / qt_sessoes` | sempre que qt_sessoes > 0 |
| `faixa_custo_hora` | `custo_total / qt_horas` | só SERVICOS_POR_HORA / SUBATIV_POR_HORA |
| `faixa_per_capita` | `custo_total / capacidade_total` | só `capacidade_confiavel = True` |

Bins: `_BINS_SESSAO/_HORA/_CAPITA` definidos no topo da cell 57. NaN → `'n/a'`.
Chamada em cell 58 após `build_hist_custo`: `tabela_base_df = add_faixas_base(tabela_base_df)`.

**Vantagem sobre hist_custo:** `tabela_base` tem `atividade_id` → drill-through funciona diretamente
ao clicar num bin. Contagem de `atividade_id` por faixa = histograma de distribuição por atividade.
Cross-filtering com qualquer slicer funciona sem relacionamento extra.

**Diferença conceitual:** `tabela_base[faixa_*]` = distribuição de atividades individuais.
`hist_custo[faixa_*]` = distribuição de métricas agregadas por grupo (uo+servico+subatividade+linguagem).

---

## Tabelas hist_ (atualmente redundantes — pendentes de limpeza)

`hist_custo` e `hist_apresentacao` foram criadas antes de `faixa_*` existir em `tabela_base`.
**Status: sobrandono notebook e no lakehouse.** Usuário pedirá limpeza geral futuramente
para remover `build_hist_custo`, `add_faixas_base` pode ficar, e simplificar o script.

`hist_apresentacao` ainda é única fonte do cruzamento Apresentação × tipologia_local (vem de
`datas_sessoes`). Se esse eixo for necessário no BI, manter; caso contrário, eliminar junto.

### Relacionamentos no modelo semântico (enquanto existirem as tabelas hist_)
- `hist_custo` e `hist_apresentacao` são ilhas — NÃO relacionar com `base`
- Para cross-filtering: relacionar via `dim_gerencia[uo]` (1:N, bidirecional)

---

## Constantes de serviço (definidas em cell 37 de nb_gold_siplan.ipynb)
```python
SERVICOS_POR_HORA = {'Curso','Oficina','Vivência','Seminário','Mediação','Visita Mediada','Intervenção urbana'}
SUBATIV_POR_HORA  = {'Multipráticas recreativas','Passeios','Viagens','Colônias recreativas'}
```

**How to apply:** Ao propor mudanças em métricas de custo, referenciar os campos canônicos de
`tabela_base` e as medidas DAX acima. Não criar colunas pré-calculadas de razão.
Relacionado: [[project_diagnostico_publico]]


<!-- ===== project_diagnostico_publico.md ===== -->

---
name: project_diagnostico_publico
description: resultados do diagnóstico D1-D4 de campos de público/capacidade no nb_gold_siplan; achados e estratégia de limpeza
metadata: 
  node_type: memory
  type: project
  originSessionId: 4f895958-7b70-4347-a211-c27bb09c0bc9
---

# Diagnóstico de campos de público/capacidade (2026-05-23)

Células D1–D4 inseridas em `nb_gold_siplan.ipynb` (cells 6–7 e 25–27). Filtro: `status_atividade IN ('PENDENTE','APROVADO')` → 33.395 de 39.144 atividades (85.3%).

## Achados principais

### D1 — Qualidade de `a.lugares` e `a.estimativa_publico`
- **AMBOS nulos: 11.5% (3.831 atividades)** → caem para `publico_sessao = 1`
- Mas: **3.148 desses têm `servico = None`** — cadastros incompletos, não erro de campo
- Mediana de `lugares` = 50; mediana de `estimativa_publico` = 50
- Outliers: 77 atividades com `lugares > 4000`, 505 com `lugares > 1000`
- Discordância > 5x entre `lugares` e `estimativa`: 236 atividades

### D2 — Diversidade de locais
- 94% das atividades têm apenas 1 local distinto → `a.lugares` representa bem
- 1.823 atividades com 2+ locais distintos (5.5%)
- 9.014 atividades com ≥1 sessão em local aberto/externo
- 4.217 atividades com ≥1 sessão em local semifixo (ginásio/quadra/piscina)
- Top tipologias: Quadra Poliesportiva, Piscina, Comedoria/Cafeteria, Sala de Múltiplo Uso, Área de Convivência

### D3 — Cruzamento capacidade × tipo de local
- **Achado contraintuitivo:** atividades SEM local aberto têm 16.7% de ambos_nulos; atividades COM local aberto têm só 3.2%
- Portanto: os nulos estão concentrados em **locais fechados** (Sala de Reunião, Sala de Múltiplo Uso, Teatro, Auditório)
- Atividades em locais semifixos têm apenas 3.1% de nulos — a variância de capacidade é esperada e os campos são preenchidos

### D4 — Serviços per-capita obrigatórios × capacidade
- **Apresentação: 46.1% com capacidade_confiavel=False** (driver: sessões em Área de Convivência, Fora da Unidade, Praça)
- **Palestra: 25.0%**
- **Oficina: 18.0%**
- **Curso: 9.9%**
- TOTAL per-capita obrigatório: 14.504 atividades; 4.222 (29.1%) com capacidade problemática
- Causa principal: sessão em local aberto/externo (27.6%), NÃO nulos de dados (1.7%)

## Estratégia de limpeza (a implementar)

| Problema | N | Tratamento |
|---|---|---|
| `servico = None` com ambos nulos | ~3.148 | Excluir do per_capita — cadastro incompleto |
| Local aberto (Área de Convivência, Praça, Fora da Unidade, Tenda) | 9.014 ativ. | `capacidade_confiavel = False`; usar estimativa se disponível, senão excluir denominador |
| Ambos zero (lugares=0 e estimativa=0) | 247 | Flag `capacidade_confiavel = False`; reportar para correção |
| Discordância > 5x entre lugares e estimativa | 236 | Flag `alerta_capacidade`; manter `lugares` como preferido |
| Outliers `lugares > 4000` | 77 | Validar manualmente; threshold 4000 parece adequado (p99=2.000) |

## Campo `capacidade_confiavel` — regra proposta
```python
# False quando: ambos nulos/zero OU tem sessão em local aberto
capacidade_confiavel = ~(
    (lugares_n.isna() | lugares_n <= 0) & (estimativa_n.isna() | estimativa_n <= 0)
    | tem_sessao_aberta
)
```

## Status (2026-05-24): IMPLEMENTADO

Todos os passos abaixo foram executados em `nb_gold_siplan.ipynb`:
1. `compute_capacidade()` criada (célula 53) — materializa os 6 campos canônicos em `tabela_base`
2. `por_sessao`, `per_capita` etc. removidos de `build_contracts` e `build_solicitacoes`
3. Medidas DAX documentadas em [[project_metricas_custo_sessao]]
4. Tabelas `hist_custo` e `hist_apresentacao` criadas (células 57-58) com bins pré-computados

**Why:** O per_capita calculado como coluna pré-calculada dá "média de razões" ao agregar por serviço/subatividade. E 29.1% das atividades per_capita têm capacidade não confiável por serem em locais sem lotação física definida.

**How to apply:** Ao propor mudanças em custo/sessão ou per_capita, considerar que `capacidade_confiavel` será o filtro no denominador do DAX.


<!-- ===== project_fabric_env.md ===== -->

---
name: Fabric environment
description: Detalhes do ambiente Microsoft Fabric para SESC-SP — endpoints, lakehouses, autenticação, padrões de escrita
type: project
originSessionId: 1e0bce95-2daf-42c9-9225-cc552d96842a
---
## SQL Endpoint (Warehouse)
`beu5bmmdbuwedpv62ucm524jzi-dmrv7k3fbwbevh5d4sidg3urfq.datawarehouse.fabric.microsoft.com`

## Lakehouses / Warehouses
- `lake_prep_siplan` — tabelas raw vindas de Dataflows Gen2
- `lake_gold_fatos` — tabelas de produção (dim_funcionarios, dim_rls_usuarios, etc.)
- ~~`lake_gold_siplan`~~ — **não existe mais** (removido em 2026-05)

## SharePoint
Site: `https://sescsp.sharepoint.com/sites/GTDadosSTS`

## Padrões de escrita nos notebooks

**Função save_gold** (definida em nb_gold_siplan, replicar se necessário):
```python
spark.createDataFrame(sanitize_for_spark(df)) \
     .write.mode('overwrite') \
     .option('overwriteSchema', 'true') \
     .saveAsTable(f'lake_gold_fatos.dbo.{table_name}')
```

**Autenticação interativa** (nb_rls_caminho — SQL endpoint):
```python
from azure.identity import DeviceCodeCredential
_cred  = DeviceCodeCredential()
_token = _cred.get_token('https://database.windows.net/.default').token
```

**Leitura SharePoint** — usar Dataflow Gen2 (não Graph API direto):
`mssparkutils.credentials.getToken('https://graph.microsoft.com')` falha com erro 500 no Fabric.
Solução adotada: Dataflow `df_corr_rls` lê SharePoint → delta tables em lake_prep_siplan → notebook lê via spark.sql.

## Notebooks principais
- `nb_gold_siplan` — constrói tabelas gold do Siplan a partir de lake_prep_siplan
- `nb_rls_usuarios` — constrói dim_rls_usuarios (RLS); roda independente
- `nb_rls_caminho` — exploração/diagnóstico do RLS (não roda em produção)
- `nb_EntregaProgs` — gera .txt das atividades, sobe SharePoint via Graph API; **não grava tabelas**; retorna JSON ao PA
- `nb_fluxo_autorizacao` — acionado pelo PA após Approval; grava analise_siplan_rps + prog_enviada; ver project_fluxo_autorizacao.md
- `nb_AnaliseSiplanRPS` — utilitário: staging lake_prep_siplan → wh_siplan_rps via JDBC overwrite
- `nb_MatrizPompeia` — matriz ações×sessões×custo por gerência/área prog → PDF no lakehouse Files


<!-- ===== feedback_fabric_notebook_format.md ===== -->

---
name: Formato obrigatório para notebooks do Fabric
description: Requisitos exatos de metadata que o Fabric exige para aceitar importação de .ipynb — sem isso dá 400 Bad Request
type: feedback
originSessionId: 17a03674-ca43-4350-a88d-7b336ee099e5
---
Ao criar notebooks `.ipynb` para importar no Microsoft Fabric, a metadata deve seguir este formato exato — qualquer desvio causa erro **400 Bad Request** no upload via UI.

**Why:** Descoberto em 2026-05-10 ao tentar importar nb_MatrizPompeia. O Fabric valida kernel e language_group antes de criar o artefato.

**How to apply:** Todo notebook criado fora do Fabric (localmente, via código) precisa ter esta estrutura antes do upload.

## Metadata do notebook (nível raiz)

```json
{
  "kernel_info": { "name": "synapse_pyspark" },
  "kernelspec": {
    "display_name": "PySpark",
    "language": "Python",
    "name": "synapse_pyspark"
  },
  "language_info": { "name": "python" },
  "microsoft": {
    "language": "python",
    "ms_spell_check": { "ms_spell_check_language": "pt" }
  },
  "nteract": { "version": "nteract-front-end@1.0.0" },
  "save_output": true,
  "spark_compute": {
    "compute_id": "/trident/default",
    "session_options": { "conf": {}, "enableDebugMode": false }
  }
}
```

## Metadata de cada célula de código

```json
{
  "microsoft": {
    "language": "python",
    "language_group": "synapse_pyspark"
  }
}
```

A célula de parâmetros (Power Automate) deve ter também `"tags": ["parameters"]`:

```json
{
  "tags": ["parameters"],
  "microsoft": { "language": "python", "language_group": "synapse_pyspark" }
}
```

Células markdown ficam com `"metadata": {}`.

## Script para corrigir um notebook existente

```python
import json

with open('meu_notebook.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

nb['metadata'] = {
    'kernel_info': {'name': 'synapse_pyspark'},
    'kernelspec': {'display_name': 'PySpark', 'language': 'Python', 'name': 'synapse_pyspark'},
    'language_info': {'name': 'python'},
    'microsoft': {'language': 'python', 'ms_spell_check': {'ms_spell_check_language': 'pt'}},
    'nteract': {'version': 'nteract-front-end@1.0.0'},
    'save_output': True,
    'spark_compute': {'compute_id': '/trident/default', 'session_options': {'conf': {}, 'enableDebugMode': False}},
}
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        tags = cell.get('metadata', {}).get('tags', [])
        cell['metadata'] = {'microsoft': {'language': 'python', 'language_group': 'synapse_pyspark'}}
        if tags:
            cell['metadata']['tags'] = tags

with open('meu_notebook.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
```


<!-- ===== feedback_fabric_write_patterns.md ===== -->

---
name: feedback-fabric-write-patterns
description: Padrões corretos de leitura e escrita Spark↔Fabric Warehouse/Lakehouse — erros encontrados e soluções
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af53e27a-45bd-4c8b-85e8-4413f9cc9e97
---

## Regras validadas em produção

### 1. Gravar tabela no Lakehouse → usar `saveAsTable` com schema `dbo`
`save("abfss://...Tables/tabela")` grava os arquivos Delta mas **não registra no catálogo** — a tabela aparece fora do `dbo`, sem preview, inacessível via SQL analytics endpoint.

**Correto:**
```python
df.write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("lake_gold_fatos.dbo.status_do_fluxo")
```

**Why:** O `saveAsTable` registra no metastore do Fabric além de gravar os arquivos. Sem o registro, o SQL analytics endpoint não enxerga a tabela.

**How to apply:** Sempre usar `saveAsTable("database.dbo.tablename")` para tabelas que precisam aparecer no modelo semântico via Direct Lake.

---

### 2. Ler do Fabric Warehouse no notebook → usar JDBC, não `spark.read.synapsesql()`
`spark.read.synapsesql()` não está disponível neste ambiente.

**Correto:**
```python
df = (spark.read
    .format('jdbc')
    .option('url', jdbc_url)
    .option('dbtable', 'dbo.tabela')
    .option('accessToken', token)
    .option('driver', 'com.microsoft.sqlserver.jdbc.SQLServerDriver')
    .load())
```

**Why:** O conector `synapsesql` não está instalado no cluster Spark deste workspace.

---

### 3. Escrever no Fabric Warehouse via JDBC → extremamente lento
Escrita JDBC Spark → Warehouse levou 16+ minutos para tabela média. Inviável para uso rotineiro.

**Solução:** Gravar Delta no Lakehouse + criar Shortcut no Warehouse apontando para a tabela.

**Why:** JDBC envia linha a linha; o SQL endpoint do Fabric tem alta latência para conexões JDBC.

---

### 4. Tipos de dados incompatíveis no JDBC para Fabric Warehouse
- `nvarchar(max)` → não suportado → usar `VARCHAR(n)` em `createTableColumnTypes`
- `datetime` → não suportado → usar `DATE` ou castear com `.cast("date")` no DataFrame
- `NVARCHAR(n)` → ParseException no Spark → usar `VARCHAR(n)` (tipo ANSI SQL)

---

### 5. Views T-SQL no warehouse → incompatíveis com Direct Lake
Não é possível adicionar views ao modelo semântico em modo Direct Lake. Usar tabela Delta física no lakehouse.

**How to apply:** Se precisar de campo calculado diário (ex: `dias_para_inicio`), computar no notebook e gravar como coluna física na tabela Delta.


<!-- ===== project_rls.md ===== -->

---
name: RLS implementation
description: Design completo do RLS no modelo semântico Fabric para SESC-SP — fontes, regras de derivação, DAX, decisões de design e problemas resolvidos
type: project
originSessionId: 1e0bce95-2daf-42c9-9225-cc552d96842a
---
## Pipeline de atualização

1. Dataflow `df_corr_rls` → lê SharePoint (rls_grupos, rls_overrides) → grava em `lake_prep_siplan`
2. Notebook `nb_rls_usuarios` → constrói `dim_rls_usuarios` → grava em `lake_gold_fatos`
3. Refresh do modelo semântico

## Listas SharePoint
Site: `https://sescsp.sharepoint.com/sites/GTDadosSTS`

**rls_grupos** — perfis estáveis (DADOS_GEDES, REPRESENTANTE)
Colunas: Título, e-mail, perfil_acesso, escopo, unidade, gerencias

**rls_overrides** — exceções individuais
Colunas: Título, e-mail, perfil_acesso, escopo, unidade, gerencias, motivo, data_fim, ativo

Convenção: `unidade = "all"` e `gerencias = "all"` significam acesso irrestrito.

## Regras de derivação de dim_funcionarios

**escopo:**
- cargo ∋ "GERENTE" AND secao ∋ "SEDE" → `GERENTE_SEDE`
- secao ∋ "SEDE" → `ADMIN_CENTRAL`
- demais → `UNIDADE`

**perfil_acesso:**
- cargo ∋ "GERENTE" → `GERENTE`
- cargo ∋ "COORD" → `COORDENADOR`
- cargo ∋ "SUPERV" → `SUPERVISOR`
- secao ∋ "PROG" AND escopo=UNIDADE → `PROGRAMADOR`
- secao ∋ "SEDE" AND cargo ∋ "TÉCNIC"/"ESPECIAL" → `ASSISTENTE`
- fallback → `GERAL` (usuário em dim_funcionarios sem classificação específica)

## Precedência das fontes

1. `rls_grupos` → **substitui** a classificação oficial para os emails presentes
2. `rls_overrides` → **acrescenta** linhas (multi-unidade via múltiplas linhas por email — Option B)
3. `dim_funcionarios` → base para todos os demais

## Decisões de design

- Multi-unidade: múltiplas linhas por email em rls_overrides (Option B), não pipe-separado em unidade
- rls_grupos pode ter unidade pipe-separada ("68|77") → notebook explode em múltiplas linhas
- GERAL não aparece nas listas SharePoint — é fallback automático do pipeline
- Admins/Members do workspace não são filtrados pelo RLS (comportamento Power BI)

## Filtros DAX no modelo semântico

Role: `RLS_Padrao` — atribuir todos os Viewers

**dim_unidade (campo `uo` — inteiro):**
```dax
VAR _email  = LOWER(USERPRINCIPALNAME())
VAR _linhas = FILTER(dim_rls_usuarios, dim_rls_usuarios[email] = _email)
RETURN
    IF(
        COUNTROWS(_linhas) = 0, FALSE(),
        IF(
            COUNTROWS(FILTER(_linhas, dim_rls_usuarios[unidade] = "all")) > 0, TRUE(),
            COUNTROWS(FILTER(_linhas, dim_rls_usuarios[unidade] = (dim_unidade[uo] & ""))) > 0
        )
    )
```

**dim_gerencia (campo `sigla` — texto):**
```dax
VAR _email   = LOWER(USERPRINCIPALNAME())
VAR _linhas  = FILTER(dim_rls_usuarios, dim_rls_usuarios[email] = _email)
VAR _gerlist = CONCATENATEX(_linhas, dim_rls_usuarios[gerencias], "|")
RETURN
    IF(
        COUNTROWS(_linhas) = 0, FALSE(),
        IF(
            CONTAINSSTRING(_gerlist, "all"), TRUE(),
            CONTAINSSTRING("|" & _gerlist & "|", "|" & dim_gerencia[sigla] & "|")
        )
    )
```

## Problemas resolvidos

- `mssparkutils.credentials.getToken('https://graph.microsoft.com')` → erro 500 no Fabric → solução: Dataflow Gen2 lê SharePoint e grava delta tables, notebook lê delta
- Campo email nas listas tem hífen: "e-mail" → renomeado para "email" no notebook
- unidade vinda do SharePoint via Dataflow é float ("82.0") → `_clean_unidade()` converte para "82"
- `VALUES()` em filtro RLS DAX → erro de tipo → substituído por `COUNTROWS(FILTER(...))`
- uo em dim_unidade é inteiro → comparação com string via `(dim_unidade[uo] & "")`

**Why:** Problemas descobertos em produção em 2026-05-09.
**How to apply:** Ao retomar o trabalho de RLS neste projeto, verificar estes pontos antes de debugar.


<!-- ===== project_fluxo_autorizacao.md ===== -->

---
name: Fluxo de autorização SiplanRPS
description: Design completo do fluxo PA → nb_EntregaProgs → Approval → nb_fluxo_autorizacao; tabelas envolvidas, regras de negócio e parâmetros
type: project
originSessionId: c0a6e7db-942c-4af2-aa36-08d247fcb0ed
---
## Visão geral

```
BI botão → PA
  └─ nb_EntregaProgs → gera .txt, sobe SharePoint
                       retorna JSON ao PA (sem gravar nada)

PA → Approvals (3 opções: Completo / Parcial / Não aprovado), timeout 24h = "Sem retorno"

  SE resultado ∈ {Completo, Parcial}:
    PA → nb_fluxo_autorizacao
         → grava analise_siplan_rps (INSERT ou UPDATE)
         → grava prog_enviada (com resultado_approval + comentario_approval)
         → retorna {"gravado": true, "resultado_approval": ..., "inseridos": X, "atualizados": Y, "ignorados": Z}
  SENÃO:
    PA encerra silenciosamente (nada gravado)
```

## Tabelas envolvidas

| Tabela | Local | Operação |
|--------|-------|----------|
| `wh_siplan_rps.dbo.analise_siplan_rps` | Fabric Warehouse | INSERT/UPDATE por nb_fluxo_autorizacao |
| `lake_relatorios_gerados.dbo.prog_enviada` | Lakehouse Delta | APPEND por nb_fluxo_autorizacao |
| `lake_gold_fatos.dbo.base` | Lakehouse Delta (read-only) | fonte dos campos das atividades |
| `lake_gold_fatos.dbo.dim_unidade` | Lakehouse Delta (read-only) | JOIN para campo `unidade` |
| ~~`lake_gold_siplan.dbo.datas_sessoes`~~ | **não existe mais** (removido 2026-05) | — |

## Regras de negócio — analise_siplan_rps

- `atividade_id` **não existe** → INSERT completo, Status = `get_status_inicial(autonomia)`
- `atividade_id` **existe** com Status ∈ `STATUSES_ATUALIZAVEIS` → UPDATE (NUNCA atualiza `custos_foto`)
- `atividade_id` **existe** com outro Status → ignorado (log apenas)

### Status inicial (INSERT)
```python
STATUS_POR_AUTONOMIA = {'UO': 'AutonomiaUO'}
STATUS_PADRAO = 'Enviado'
```
- autonomia = `'UO'` → Status = `'AutonomiaUO'`
- qualquer outra → Status = `'Enviado'`

### Status que permitem UPDATE
```python
STATUSES_ATUALIZAVEIS = {'Enviado', 'Reenviado', 'Em Revisão'}
```

### Resultado do Approval que dispara gravação
```python
RESULTADOS_GRAVAM = {'Completo', 'Parcial'}
```
- `'Não aprovado'` e `'Sem retorno'` → saída silenciosa, nada gravado

## Mapeamento de campos — analise_siplan_rps

| Campo tabela | Fonte | Observação |
|---|---|---|
| `atividade_id` | `base.atividade_id` | |
| `nome` | `base.nome` | |
| `Título` | `base.nome` | campo SharePoint obrigatório |
| `unidade` | `dim_unidade.unidade` | JOIN ON CAST(LEFT(CAST(atividade_id,2),INT) = uo |
| `gerencia` | `base.gerencia` | |
| `area` | `base.areaprog` | |
| `linguagem` | `base.linguagem` | |
| `mes` | `base.mes` | |
| `autonomia` | `base.autonomia` | |
| `dataPrimeiraSessao` | `base.PrimeiraData` | |
| `custos_foto` | multiline (veja abaixo) | INSERT apenas, NUNCA atualizado |
| `custos_editavel` | multiline (veja abaixo) | INSERT e UPDATE |
| `data_entrega` | `datetime.now()` | |
| `quem` | parâmetro `solicitante` | |
| `Criado por` | parâmetro `solicitante` | INSERT apenas |
| `Criado` | `datetime.now()` | INSERT apenas |
| `Status` | `get_status_inicial(autonomia)` | INSERT apenas |

### Conteúdo de custos_foto / custos_editavel (multilinha)
```
{dataPrimeiraSessao}
{complemento}
{item_desc}
{projeto_nome}
{MAX(datas_sessoes.localNome)} - {precificacao_desc}
```

## Campos extras em prog_enviada (novos)

`resultado_approval` e `comentario_approval` — adicionados via `mergeSchema=True` na primeira execução.

## Parâmetros injetados pelo PA em nb_fluxo_autorizacao

```
atividade_ids_str    — CSV ou JSON array de IDs
solicitante          — email do solicitante
resultado_approval   — Completo | Parcial | Não aprovado | Sem retorno
comentario_approval  — texto livre do aprovador
relatorio_id         — UUID gerado por nb_EntregaProgs
relatorio_url        — URL do arquivo no SharePoint
relatorio_nome       — 'Entrega da Programação para a STS'
gerencias            — pipe-separated, gerado por nb_EntregaProgs
qt_total             — int, gerado por nb_EntregaProgs
data_geracao         — ISO string (gerado_em de nb_EntregaProgs)
```

## Retorno de nb_EntregaProgs ao PA (inalterado)

```json
{
  "relatorio_id": "...",
  "relatorio_nome": "Entrega da Programação para a STS",
  "url": "https://...",
  "qt_total": 3,
  "gerencias": "GER-A|GER-B",
  "gerado_em": "2026-05-14T10:30:00"
}
```
`registrar_relatorio()` foi comentado — log só é gravado após Approval.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `novo_siplanRPS/nb_EntregaProgs.ipynb` | `registrar_relatorio()` comentado na célula `execucao` |
| `novo_siplanRPS/nb_fluxo_autorizacao.ipynb` | Notebook completo (novo) — 6 células |
| `novo_siplanRPS/nb_AnaliseSiplanRPS.ipynb` | Notebook utilitário (backup) — lê staging → grava warehouse via JDBC |

## Risco conhecido

`spark.sql(INSERT/UPDATE)` em Fabric Warehouse ainda não testado neste ambiente.
`_exec_sql()` está isolado — se falhar, trocar por JDBC em nb_AnaliseSiplanRPS.

**Why:** Design separado para desacoplar geração do arquivo do log de entrega, garantindo que nada seja gravado sem aprovação explícita.
**How to apply:** Ao sugerir mudanças no fluxo PA, respeitar que nb_EntregaProgs nunca grava — só nb_fluxo_autorizacao o faz, e só após Approval.


<!-- ===== project_entrega_progs_flow.md ===== -->

---
name: entrega-progs-flow
description: "Fluxo PA→nb_EntregaProgs→OneLake→e-mail: arquitetura validada, armadilhas resolvidas em 2026-05-15"
metadata: 
  node_type: memory
  type: project
  originSessionId: d1ef0ec0-f9b4-4468-afea-fbcae9fd6fbc
---

## Fluxo validado (2026-05-15, ampliado 2026-05-15)

```
Botão BI → PA
  POST → nb_EntregaProgs (injeta atividade_ids_str, solicitante)
    retorna 200 Completed (síncrono — sem DO UNTIL)
  GET _output.json do OneLake → metadados
  GET .txt do OneLake → conteúdo
  Compose (base64ToString) → corpo do e-mail
  Upload .txt → SharePoint (PA já sabe fazer)
  Approval → nb_fluxo_autorizacao
```

## Armadilhas resolvidas

### 1. POST pode retornar Completed ou InProgress — DO UNTIL necessário
A API `POST /jobs/instances?jobType=RunNotebook` pode retornar **200 Completed** diretamente (runs curtas) ou o job ainda estar `InProgress` quando o GET de polling é chamado.

**Arquitetura correta:**
```
POST → inicia o job
DO UNTIL (status == "Completed"):
  GET /jobs/instances/{id}   ← usa jobInstanceId do body do POST
  delay 90s entre tentativas
GET _output.json → ler metadados
```
O `jobInstanceId` vem do campo `id` no body do POST (não do header Location, que não existe).
O endpoint `/jobs/instances/{id}/output` retorna 404 — não usar.

**Solução para obter dados do notebook:** arquivo `_output.json` gravado no lakehouse.

### 2. mssparkutils.fs.put trunca em newlines
`mssparkutils.fs.put(path, content, overwrite=True)` salva apenas a primeira linha do conteúdo.

**Solução:** usar Hadoop API diretamente:
```python
abfss = f'abfss://{ONELAKE_WORKSPACE}@onelake.dfs.fabric.microsoft.com/{ONELAKE_LAKEHOUSE}/{dest}'
jvm  = spark._jvm
conf = spark._jsc.hadoopConfiguration()
path = jvm.org.apache.hadoop.fs.Path(abfss)
fs   = path.getFileSystem(conf)
out  = fs.create(path, True)
out.write(local_path.read_bytes())
out.close()
```

### 3. Audience errado no GET do OneLake
OneLake (ADLS Gen2 endpoint) exige audience diferente da Fabric API.

| Endpoint | Audience |
|---|---|
| `api.fabric.microsoft.com` | `https://api.fabric.microsoft.com` |
| `onelake.dfs.fabric.microsoft.com` | **`https://storage.azure.com/`** |

### 4. Body do OneLake vem em base64
GET ao OneLake retorna `Content-Type: application/octet-stream` com `$content` em base64.

**No PA — Parse JSON:**
- Content: `base64ToString(body('HTTP_GET_Status')['$content'])`
- Schema: definir campos esperados do JSON

**Para o .txt:**
- Compose: `base64ToString(body('HTTP_GET_TXT')['$content'])`

### 5. atividade_id é DECIMAL — sem aspas no Spark SQL
```python
# ERRADO (retorna 0 linhas para coluna DECIMAL):
ids_sql = ','.join("'" + str(i) + "'" for i in ids)

# CORRETO:
ids_sql = ', '.join(str(int(i)) for i in ids)
```

### 6. /lakehouse/default/ aponta para lakehouse errado
Usar ABFSS URI com IDs hardcoded — não depender do mount default.

```python
ONELAKE_WORKSPACE = 'ab5f231b-0d65-4a82-9fa3-e490336e912c'
ONELAKE_LAKEHOUSE = '59d32952-1672-4252-8c46-ff074684ed8e'
```

### 7. Graph API 401 — SP sem Application permissions
Notebook não deve fazer upload direto ao SharePoint via Graph API.
**Solução adotada:** notebook salva no lakehouse, PA faz o upload (que já sabe fazer).

## URLs OneLake (fixas)
```
_output.json:
https://onelake.dfs.fabric.microsoft.com/ab5f231b-0d65-4a82-9fa3-e490336e912c/59d32952-1672-4252-8c46-ff074684ed8e/Files/entrega_progs/_output.json

.txt (dinâmico):
https://onelake.dfs.fabric.microsoft.com/ab5f231b-0d65-4a82-9fa3-e490336e912c/59d32952-1672-4252-8c46-ff074684ed8e/Files/entrega_progs/@{body('Parse_JSON')?['filename']}
```

## _output.json — campos (atualizado)
```json
{
  "relatorio_id", "relatorio_nome",
  "filename",      "lh_path",       // .txt
  "filename_html", "lh_path_html",  // .html (novo)
  "unidade", "gerencias",           // pipe-separated
  "qt_total", "gerado_em"
}
```

## Novas tabelas consultadas por nb_EntregaProgs (2026-05-15)
- `lake_gold_fatos.dbo.datas_sessoes` → qt_sessoes + localNome_max (mais frequente por atividade)
- `lake_gold_fatos.dbo.solicitacoes`  → grupo, custo, alerta, sem_pcap, sem_pax

**Nota:** `datas_sessoes` está em `lake_gold_fatos.dbo` (NÃO em lake_gold_siplan que não existe mais).
`nb_fluxo_autorizacao.ipynb` ainda referencia `lake_gold_siplan.dbo.datas_sessoes` — pendente correção.

## Estrutura do relatório gerado (atualizado 2026-05-16)

### Cabeçalho (ambos os formatos)
```
Sesc {unidade}
REVISÃO PARA ENTREGA DA PROGRAMAÇÃO PARA A STS
Gerado em dd/mm/yyyy HH:MM por {solicitante}
```
- `unidade` vem de `dim_unidade.unidade` via JOIN no `fetch_atividades`
- `solicitante` = email do Power Automate (parâmetro `solicitante`)

### Seções sumárias (TXT e HTML)
1. Resumo (n ações, n gerências, total contratos, total geral, breakdown por mês)
2. Por Gerência — tabela: Gerência | Ações | Sessões | Contratos | Total
3. Por Linguagem — tabela: Linguagem | Ações | Sessões | Contratos | Total
4. Por Item de Custo — agrupa `df_solic` por `grupo`; tabela: Grupo | Ações | Sessões | Valor
5. Projetos Relevantes — filtra `projeto NOT NULL/vazio`, aplica limiares `PROJ_MIN_ACOES`/`PROJ_MIN_TOTAL`
6. Alertas totalizadores (resumo macro por tipo)

### Limiares para Projetos Relevantes (configuráveis)
```python
PROJ_MIN_ACOES = 5          # produção: 10
PROJ_MIN_TOTAL = 10_000     # produção: 100_000
```
Definidas no topo da célula `gerar-txt`; usadas em ambas as funções.

### Grupos de solicitação
```python
GRUPOS_CONTRATO   = ('Contrato PJ', 'Contrato PF', 'Contrato Cooperativa')
GRUPOS_PASSAGEM   = ('Passagem Aérea',)
GRUPOS_HOSPEDAGEM = ('Hospedagem',)
```

### fetch_solicitacoes — schema atual
```python
GROUP BY atividade_id, grupo, complemento   # complemento é PCAP/trechos/passageiros
```
Colunas: `atividade_id, grupo, complemento, custo_grupo, tem_alerta, n_solic, sem_pcap, sem_pax`
- `sem_pcap`: contratos onde `complemento IS NULL OR LENGTH(TRIM(complemento)) < 3`
- `sem_pax`: passagem/hospedagem onde `publico_sessao IS NULL OR publico_sessao = 0`

### Sistema de alertas: _build_ativ_alertas()
Retorna `{atividade_id (int): [lista de strings]}`. Combina três fontes:
1. **Solicitações** — por grupo, por linha de `df_solic`:
   - `sem_pcap > 0` → `'{grupo}: falta informar PCAP'`
   - `sem_pax > 0` → usa `_MSG_PAX` dict (Passagem→'passageiros e/ou trechos', Hospedagem→'trechos')
   - `tem_alerta > 0` e sem sem_pcap/sem_pax → `'{grupo}: alerta na solicitação'`
2. **Justificativa** — `df_m.justificativa` nulo/vazio → `'justificativa não informada'`
3. **Precificação** — `precificacao_desc` nulo/vazio/S/I → `'precificação vazia ou S/I'`

Atividade com qualquer alerta recebe `[!]` na linha de data no TXT.

### TXT — bloco de ação individual (autonomia != UO)
```
dd/mm/yyyy [!]           ← data 1ª sessão + flag se há alertas
N sessões / sessão única
Nome — complemento       ← complemento da tabela base (descrição da ação)
nome do projeto          ← omitido se vazio/NaN
area | linguagem         ← se iguais, mostra só uma vez
Contrato PJ  PCAP-123  R$ 21.000,00   ← grupo + complemento_solic + valor (1 linha por df_solic)
Hospedagem  R$ 2.700,00               ← complemento omitido se vazio
local — precificação     ← omitido se ambos vazios
[!] alerta 1
[!] alerta 2
                         ← linha em branco separadora
```

### TXT — bloco de ação individual (autonomia == UO)
One-liner: `dd/mm/yyyy  N sessões  Nome  R$ total [!]`
Seguido de linhas `    [!] alerta` (indentadas) se houver alertas.

### Estrutura de seções no TXT/HTML — por autonomia
```python
for aut in sorted(df_m['autonomia'].dropna().unique()):
    out.extend(_bloco(df_m[df_m['autonomia'] == aut], aut, aut))
sem_aut = df_m[df_m['autonomia'].isna()]
if not sem_aut.empty:
    out.extend(_bloco(sem_aut, 'SEM AUTONOMIA', 'SEM AUTONOMIA'))
```
Dentro de cada seção: agrupa por `gerencia` (sort=True), depois ordena por `dataPrimeiraSessao` crescente.

### HTML — tabela de ações
17 colunas: `#, ID, Nome, Gerência, Área, Ling., Mês, Unidade, 1ª Sessão, Sessões, Projeto, Item/Complemento, Local, Justificativa, Contratos, Total, Alertas`
- Linha com `ativ_alertas[aid]` não-vazio → fundo `#fff2cc`
- `Alertas` = string com todos os alertas separados por ` | `

## Campos financeiros em base
- `custo_contratos_total` = valor contratos
- `custo_total` = valor total (todos os custos)

### 8. CAST(atividade_id AS STRING) no Spark produz notação científica
`CAST(63000016479883 AS STRING)` em coluna numérica Spark retorna `'6.3E+13'`.
`LEFT(..., 2)` pega `'6.'` → `CAST AS INT` → `6` (errado).

**Solução (célula `fetch-atividades`, JOIN com `dim_unidade`):**
```sql
-- ERRADO:
CAST(LEFT(CAST(b.atividade_id AS STRING), 2) AS INT) = du.uo
-- CORRETO:
CAST(LEFT(CAST(CAST(b.atividade_id AS BIGINT) AS STRING), 2) AS INT) = du.uo
```

### 9. Não editar o notebook diretamente no Fabric — sempre republicar do local
Edições feitas direto no Fabric (ex: `rid = str(uuid.uuid4())` inserido como teste)
não aparecem no arquivo local e causam bugs silenciosos. O arquivo local é a fonte de verdade.

**Why:** fluxo tomou vários ciclos de debugging — registrar para não repetir.
**How to apply:** ao retomar nb_EntregaProgs, partir deste estado funcional.


<!-- ===== project_status_do_fluxo.md ===== -->

---
name: project-status-do-fluxo
description: "Notebook que gera status_do_fluxo — arquitetura, bug corrigido, campos de prazo adicionados"
metadata: 
  node_type: memory
  type: project
  originSessionId: af53e27a-45bd-4c8b-85e8-4413f9cc9e97
---

## Tabela `lake_gold_fatos.dbo.status_do_fluxo`

Tabela Delta no lakehouse que consolida o status de cada atividade no fluxo de autorização, incluindo "Não enviadas". Atualizada diariamente via notebook Spark.

**Destino:** `saveAsTable("lake_gold_fatos.dbo.status_do_fluxo")`

---

## Fontes

| Fonte | O que traz | Como lê |
|---|---|---|
| `lake_gold_fatos.dbo.base` | `atividade_id`, `autonomia`, `PrimeiraData` | `spark.sql()` |
| `wh_siplan_rps.dbo.analise_siplan_rps` | `atividade_id`, `autonomia`, `Status` (editado pelos usuários) | JDBC |

**Filtro:** `year(PrimeiraData) >= year(current_date())` — atividades do ano corrente em diante.

---

## Bug corrigido (2026-05-25)
O notebook original lia `analise_siplan_rps` de `lake_gold_fatos` (lakehouse, staging sem edições dos usuários) em vez de `wh_siplan_rps` (warehouse, onde os usuários alteram o Status). Resultado: coluna `StatusGeral` sempre mostrava o valor do staging, ignorando aprovações/rejeições registradas no warehouse.

---

## Campos adicionados (2026-05-25)

| Campo | Tipo | Lógica |
|---|---|---|
| `PrimeiraData` | DATE | Castear com `.cast("date")` antes do join para evitar erro `datetime` no JDBC |
| `dias_para_inicio` | INT | `F.datediff(F.col("PrimeiraData"), F.current_date())` — positivo = futuro, negativo = já ocorreu |
| `faixa_prazo` | VARCHAR(20) | Bucket exclusivo com prefixo numérico para ordenação correta no slicer |

**Buckets `faixa_prazo`:**
- `0. Já ocorreu` → dias < 0
- `1. ≤10 dias` → 0–10
- `2. ≤20 dias` → 11–20
- `3. ≤30 dias` → 21–30
- `4. ≤45 dias` → 31–45
- `5. ≤60 dias` → 46–60
- `6. 60+ dias` → > 60

---

## Uso no modelo semântico
- `faixa_prazo` → slicer de lista (selecionar múltiplos para efeito cumulativo)
- `dias_para_inicio` → slicer de intervalo numérico (arrastar máximo para 10, 20, 30...)
- Shortcut no `wh_siplan_rps` apontando para `lake_gold_fatos.dbo.status_do_fluxo` para acesso via SQL endpoint do warehouse

**Why:** Views T-SQL são incompatíveis com Direct Lake — campos calculados devem ser colunas físicas na tabela Delta. Ver [[feedback-fabric-write-patterns]].


<!-- ===== project_matriz_pompeia.md ===== -->

---
name: nb_MatrizPompeia — estado atual
description: Notebook que gera PDF com matriz ações×sessões×custo por gerência e área programática para a UO Pompeia/Maio — o que foi feito, o que falta validar
type: project
originSessionId: 17a03674-ca43-4350-a88d-7b336ee099e5
---
## O que é

`novo_siplanRPS/nb_MatrizPompeia.ipynb` — gera um PDF de uma página com tabela estilo "heatmap-barra" agrupada por gerência e área programática.

Colunas da tabela: **áreas programáticas | ações (barra laranja + nº) | sessões (barra vermelha + nº) | custo (R$)**

## Fluxo de dados

1. Lê IDs de `ids_pompeia_maio.csv` (60 IDs) — localmente do CSV, no Fabric de `/lakehouse/default/Files/ids_pompeia_maio.csv` ou via parâmetro Power Automate (`atividade_ids_str`)
2. Query: `lake_gold_fatos.tabela_base` filtrando pelos IDs
   - Colunas usadas: `atividade_id`, `areaprog`, `gerencia`, `qt_sessoes`, `custo_total`
3. Agrupa: `nunique(atividade_id)` → ações, `sum(qt_sessoes)` → sessões, `sum(custo_total)` → custo
4. Ordena gerências na sequência: GDFE, GEAVT, GEPROS, GESC, GSO, GEAC, GECOM

## Geração do PDF

- Salva em `/tmp/` (Linux/Fabric) ou `tempfile.gettempdir()` (Windows/local)
- Copia para `Files/matriz_pompeia_maio.pdf` via `mssparkutils.fs.cp(f'file://{TMP_PATH}', 'Files/...', overwrite=True)`
- Retorna JSON via `mssparkutils.notebook.exit()`

## Estado em 2026-05-10

- ✅ Notebook criado e validado localmente (com dados de simulação = números da imagem de referência)
- ✅ PDF gerado corretamente (39 KB, visual correto com barras inline)
- ✅ Metadata corrigida para importação no Fabric (ver `feedback_fabric_notebook_format.md`)
- ⏳ **Falta:** rodar no Fabric com dados reais e verificar se `areaprog` e `gerencia` estão preenchidos corretamente na `tabela_base` para os 60 IDs da Pompeia

## Dados de simulação (hardcoded como fallback)

Quando `FABRIC_ENV = False` ou `spark.table()` falha, usa SIM_DATA com os valores da imagem de referência (GDFE/Físico-Esportivo: 22 ações, 100 sessões, R$228.590 etc.).

**Why:** O notebook precisa rodar localmente para testes visuais sem acesso ao Fabric.

**How to apply:** Ao continuar o trabalho, primeiro subir o notebook para o Fabric e rodar com os IDs reais. Se os campos `areaprog`/`gerencia` vierem nulos, investigar na `tabela_base` — pode ser que esses IDs da Pompeia não tenham gerência mapeada (ver nb_gold_siplan célula "Define as gerências", mapa GERENCIA_POR_AREAPROG).
