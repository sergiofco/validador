# Contexto do Fluxo de Autorização — SiplanRPS

> Arquivo portátil para onboarding em nova máquina / nova sessão de IA.
> Gerado em 2026-05-14. Projeto: SESC-SP / GT Dados.

---

## 1. Ambiente Microsoft Fabric

| Item | Valor |
|---|---|
| SQL Endpoint | `beu5bmmdbuwedpv62ucm524jzi-dmrv7k3fbwbevh5d4sidg3urfq.datawarehouse.fabric.microsoft.com` |
| Warehouse | `wh_siplan_rps` |
| SharePoint site | `https://sescsp.sharepoint.com/sites/GTDadosSTS` |

### Lakehouses / Warehouses usados

| Nome | Uso |
|---|---|
| `lake_gold_fatos` | Tabelas de produção — `base`, `dim_unidade` |
| `lake_gold_siplan` | `datas_sessoes` (MAX localNome para custos) |
| `lake_relatorios_gerados` | `prog_enviada` — log de entregas |
| `lake_prep_siplan` | Staging de Dataflows Gen2 |
| `wh_siplan_rps` | Warehouse — `analise_siplan_rps` |

---

## 2. Fluxo completo Power Automate

```
Usuário (botão no BI)
  └─► PA dispara nb_EntregaProgs
        • Busca atividades em lake_gold_fatos.dbo.base
        • Gera arquivo .txt
        • Sobe ao SharePoint via Graph API (Service Principal)
        • NÃO grava em nenhuma tabela
        • Retorna JSON:
            { "relatorio_id": "...", "relatorio_nome": "...",
              "url": "...", "qt_total": N,
              "gerencias": "A|B", "gerado_em": "ISO" }

PA → Approvals (envia URL do arquivo)
  Opções: Completo | Parcial | Não aprovado
  Timeout 24h → "Sem retorno"

  SE resultado ∈ {Completo, Parcial}
    └─► PA dispara nb_fluxo_autorizacao
          • Grava analise_siplan_rps (INSERT ou UPDATE)
          • Grava prog_enviada (com resultado_approval + comentario_approval)
          • Retorna: {"gravado": true, "resultado_approval": "...",
                      "inseridos": X, "atualizados": Y, "ignorados": Z}
  SENÃO (Não aprovado | Sem retorno)
    └─► PA encerra — nada gravado
```

---

## 3. Notebooks — localização e responsabilidade

| Notebook | Arquivo | O que faz |
|---|---|---|
| nb_EntregaProgs | `novo_siplanRPS/nb_EntregaProgs.ipynb` | Gera .txt + sobe SharePoint. Retorna JSON ao PA. **Não grava tabelas.** |
| nb_fluxo_autorizacao | `novo_siplanRPS/nb_fluxo_autorizacao.ipynb` | Grava analise_siplan_rps + prog_enviada **após Approval**. |
| nb_AnaliseSiplanRPS | `novo_siplanRPS/nb_AnaliseSiplanRPS.ipynb` | Utilitário backup: staging → warehouse via JDBC overwrite. |

---

## 4. nb_fluxo_autorizacao — células e responsabilidade

| Célula (id) | Tipo | O que faz |
|---|---|---|
| `md-titulo` | markdown | Documentação do fluxo |
| `parametros` | code | Todos os parâmetros injetáveis pelo PA |
| `imports` | code | Imports, detecção FABRIC_ENV / HAS_MSSPARKUTILS |
| `auth-helpers` | code | `_get_db_conn()` — autenticação local via pyodbc |
| `fetch-atividades` | code | `fetch_atividades(ids)` — busca em lake_gold_fatos |
| `helpers` | code | `_build_custos`, `get_status_inicial`, `_sql_val`, `_exec_sql`, `_query_existentes`, **`registrar_entrega()`** |
| `registrar-analise` | code | `registrar_analise()` — INSERT/UPDATE em analise_siplan_rps; retorna dict de contagens |
| `execucao` | code | Lógica principal: verifica Approval → fetch → registrar_analise → registrar_entrega → exit |

---

## 5. Parâmetros injetados pelo PA em nb_fluxo_autorizacao

```python
atividade_ids_str    = ''   # CSV ou JSON array  ex: '123,456' ou '[{"atividade_id":123}]'
solicitante          = ''   # email do solicitante
resultado_approval   = ''   # Completo | Parcial | Não aprovado | Sem retorno
comentario_approval  = ''   # texto livre do aprovador
relatorio_id         = ''   # UUID de nb_EntregaProgs
relatorio_url        = ''   # URL SharePoint de nb_EntregaProgs
relatorio_nome       = 'Entrega da Programação para a STS'
gerencias            = ''   # ex: 'GER-A|GER-B'
qt_total             = 0
data_geracao         = ''   # ISO string — gerado_em de nb_EntregaProgs
```

---

## 6. Regras de negócio — analise_siplan_rps

### Status inicial no INSERT

```python
STATUS_POR_AUTONOMIA = {'UO': 'AutonomiaUO'}
STATUS_PADRAO = 'Enviado'
# autonomia='UO' → Status='AutonomiaUO'
# qualquer outra → Status='Enviado'
```

### Quando permite UPDATE

```python
STATUSES_ATUALIZAVEIS = {'Enviado', 'Reenviado', 'Em Revisão'}
# linha com outro Status → ignorada (log apenas)
```

### Quando grava (gate do Approval)

```python
RESULTADOS_GRAVAM = {'Completo', 'Parcial'}
# 'Não aprovado' e 'Sem retorno' → retorna {"gravado": false}, nada escrito
```

### Regra do custos_foto

- Calculado igual a `custos_editavel` no INSERT
- **NUNCA atualizado** nos UPDATEs seguintes

---

## 7. Mapeamento de campos — analise_siplan_rps

| Campo | Fonte SQL | Nota |
|---|---|---|
| `atividade_id` | `base.atividade_id` | |
| `nome` | `base.nome` | |
| `Título` | `base.nome` | campo SharePoint obrigatório |
| `unidade` | `dim_unidade.unidade` | JOIN ON `b.uo = du.uo` (coluna direta de `base`, sem derivação por prefixo) |
| `gerencia` | `base.gerencia` | |
| `area` | `base.areaprog` | |
| `linguagem` | `base.linguagem` | |
| `mes` | `base.mes` | |
| `autonomia` | `base.autonomia` | |
| `dataPrimeiraSessao` | `base.PrimeiraData` | |
| `custos_foto` | multiline (ver abaixo) | **INSERT only** |
| `custos_editavel` | multiline (ver abaixo) | INSERT + UPDATE |
| `data_entrega` | `datetime.now()` | |
| `quem` | parâmetro `solicitante` | |
| `Criado por` | parâmetro `solicitante` | INSERT only |
| `Criado` | `datetime.now()` | INSERT only |
| `Status` | `get_status_inicial(autonomia)` | INSERT only |

### Conteúdo multilinha de custos

```
{dataPrimeiraSessao}
{complemento}
{item_desc}
{projeto_nome}
{MAX(datas_sessoes.localNome)} - {precificacao_desc}
```
(linhas em branco são omitidas)

---

## 8. prog_enviada — campos novos

Adicionados com `mergeSchema=True` (Spark Delta) na primeira execução de nb_fluxo_autorizacao:

| Campo | Tipo | Origem |
|---|---|---|
| `resultado_approval` | string | parâmetro PA |
| `comentario_approval` | string | parâmetro PA |

Os demais campos já existiam: `relatorio_id`, `relatorio_nome`, `data_geracao`, `url_arquivo`, `solicitante`, `atividade_ids`, `qt_total`, `gerencias`.

---

## 9. Autenticação

| Contexto | Método |
|---|---|
| Fabric (FABRIC_ENV=True) | `spark.sql()` para DML; `spark.createDataFrame().write` para Delta |
| Local (dev) | `pyodbc` + `InteractiveBrowserCredential` / `DeviceCodeCredential` |
| Graph API (SharePoint upload) | `ClientSecretCredential` com SP do Power Automate |

**Atenção:** `mssparkutils.credentials.getToken('https://graph.microsoft.com')` falha com erro 500 neste ambiente. Sempre usar `ClientSecretCredential` para Graph.

---

## 10. Riscos / pontos de atenção

| Risco | Mitigação |
|---|---|
| `spark.sql(INSERT/UPDATE)` no Warehouse não testado | `_exec_sql()` isolada — se falhar, trocar por JDBC |
| `mergeSchema=True` em prod | Primeira execução cria colunas novas em `prog_enviada` automaticamente |
| Timeout Approval 24h sem retorno | PA retorna "Sem retorno" → nb_fluxo_autorizacao sai com `{"gravado": false}` |

---

## 11. Checklist de testes

- [ ] `nb_EntregaProgs` → confirmar que `prog_enviada` **não** é gravada
- [ ] `nb_fluxo_autorizacao` com `resultado_approval='Não aprovado'` → `{"gravado": false}`, nada gravado
- [ ] `nb_fluxo_autorizacao` com `resultado_approval='Completo'` + ID novo → INSERT em `analise_siplan_rps` + linha em `prog_enviada`
- [ ] Mesmo ID novamente + `resultado_approval='Parcial'` → UPDATE em `analise_siplan_rps` + nova linha em `prog_enviada`
- [ ] Verificar colunas `resultado_approval` e `comentario_approval` em `prog_enviada`
- [ ] Atividade com Status fora de `STATUSES_ATUALIZAVEIS` → ignorada no log
- [ ] Atividade com autonomia='UO' → Status='AutonomiaUO' no INSERT
