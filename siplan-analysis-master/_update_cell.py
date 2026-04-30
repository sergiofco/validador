import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'c:/Users/INTEL/Documents/EstudoTemporal/analise_longitudinal.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

# ── Diagnóstico Cinesesc corrigido (sem ano_mes) ───────────────────────────────
new_diag = """\
# ── Diagnóstico: Cinesesc – presentes por ano nas diferentes bases ─────────────

# 1. Quantos espaços Cinesesc em _local_meses
_cin_lm = _local_meses[_local_meses['local_grupo'] == 'Cinesesc']
print(f'Espacos Cinesesc em _local_meses: {len(_cin_lm)}')
display(_cin_lm[['unidade', 'local_nome', 'percentual', 'meses_com_sessao', 'selecao']].reset_index(drop=True))

# 2. Presentes Cinesesc na base BRUTA por ano (via datainicio)
print('\\nPresentes Cinesesc - base bruta (df_raw_acoes_preview), por ano:')
_cin_raw = df_raw_acoes_preview[df_raw_acoes_preview['local_grupo_apresentacoes'] == 'Cinesesc'].copy()
_cin_raw['presentes'] = pd.to_numeric(_cin_raw['presentes'], errors='coerce').fillna(0)
_cin_raw['_ano'] = pd.to_datetime(_cin_raw['datainicio'], errors='coerce').dt.year
_por_ano_bruto = (
    _cin_raw[_cin_raw['_ano'].between(2018, 2025)]
    .groupby('_ano')
    .agg(sessoes=('sessao_id', 'nunique'), presentes=('presentes', 'sum'))
    .reset_index()
)
display(_por_ano_bruto)

# 3. Presentes Cinesesc em df_apresentacoes (100 recorrentes) por ano
print('\\nPresentes Cinesesc - df_apresentacoes (recorrentes), por ano:')
_cin_ap = df_apresentacoes[df_apresentacoes['local_grupo_apresentacoes'] == 'Cinesesc'].copy()
_cin_ap['presentes'] = pd.to_numeric(_cin_ap['presentes'], errors='coerce').fillna(0)
_cin_ap['_ano'] = pd.to_datetime(_cin_ap['datainicio'], errors='coerce').dt.year
_por_ano_ap = (
    _cin_ap[_cin_ap['_ano'].between(2018, 2025)]
    .groupby('_ano')
    .agg(sessoes=('sessao_id', 'nunique'), presentes=('presentes', 'sum'))
    .reset_index()
)
display(_por_ano_ap)
print(f'Total presentes Cinesesc em df_apresentacoes: {_por_ano_ap[\"presentes\"].sum():,.0f}')

# 4. Colunas disponíveis em df_apresentacoes (para referência)
print('\\nColunas em df_apresentacoes:')
print(list(df_apresentacoes.columns))
"""

# ── comparativo_periodos: corrige extração de ano via datainicio ───────────────
for cell in nb['cells']:
    src = cell['source'] if isinstance(cell['source'], str) else ''.join(cell['source'])
    if cell.get('id') == 'comparativo_periodos':
        # Substitui bloco de extração de ano
        old_blk = (
            "# Extrai ano\n"
            "if 'ano_mes' in _df.columns:\n"
            "    try:\n"
            "        _df['_ano'] = _df['ano_mes'].dt.year\n"
            "    except AttributeError:\n"
            "        _df['_ano'] = _df['ano_mes'].astype(str).str[:4].astype(int)\n"
            "else:\n"
            "    _df['_ano'] = pd.to_datetime(_df['datainicio'], errors='coerce').dt.year\n"
        )
        new_blk = "_df['_ano'] = pd.to_datetime(_df['datainicio'], errors='coerce').dt.year\n"
        if old_blk in src:
            src = src.replace(old_blk, new_blk)
            cell['source'] = src
            cell['outputs'] = []
            cell['execution_count'] = None
            print('comparativo_periodos: extracao de ano corrigida para datainicio.')
        else:
            print('AVISO: bloco de ano nao encontrado em comparativo_periodos.')
            # tenta corrigir mais diretamente
            import re
            src2 = re.sub(
                r"# Extrai ano\nif 'ano_mes'.*?dt\.year\n",
                "_df['_ano'] = pd.to_datetime(_df['datainicio'], errors='coerce').dt.year\n",
                src, flags=re.DOTALL
            )
            if src2 != src:
                cell['source'] = src2
                cell['outputs'] = []
                cell['execution_count'] = None
                print('  -> corrigido via regex.')
            else:
                print('  -> nao foi possivel corrigir automaticamente.')

    if cell.get('id') == 'diag_cinesesc':
        cell['source'] = new_diag
        cell['outputs'] = []
        cell['execution_count'] = None
        print('diag_cinesesc: atualizado para usar datainicio.')

with open(r'c:/Users/INTEL/Documents/EstudoTemporal/analise_longitudinal.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print('Notebook salvo.')
