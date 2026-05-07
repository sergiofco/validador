"""
Classificação de mensuradores por subatividade — RPS Sesc SP
Fonte normativa: Guia RPS no DR SP v1.0, set/2024 (vigência 2025+)

Uso em notebooks Fabric:
    from mensuradores import coluna_presenca, ESPECIFICAS, eh_especifica

A chave de classificação é `modalidade_desc` (SUBATIVIDADE no RPS),
campo presente em siplan_lancamento_mensurador e tabelas derivadas.
"""

# ---------------------------------------------------------------------------
# Regras de equivalência
# ---------------------------------------------------------------------------

# Subatividades onde "Pessoas atendidas" equivale a Presenças
EQUIVALE_PESSOAS_ATENDIDAS: set[str] = {
    "Consulta",
    "Lanche",
    "Refeição",
}

# Subatividades onde "Inscritos no dia" equivale a Presenças
EQUIVALE_INSCRITOS_DIA: set[str] = {
    "Hospedagem",
}

# Subatividades específicas: sem mensurador de presença (excluir de análises
# que dependem de contagem de público)
ESPECIFICAS: set[str] = {
    # Alimentação — produto contado por quantidade, não por pessoa
    "Produtos Gastronômicos",
    # Saúde — procedimentos clínicos e diagnósticos
    "Análise de risco em saúde",
    "Sessão diagnóstica/clínica",
    "Procedimentos diagnósticos por imagem",
    "Procedimentos clínicos",
    "Procedimentos complementares",
    # Biblioteca / Acervo — acessos, não presenças
    "Acervo e Recursos Informacionais",
    # Assistência — tonelagem, doadores, entidades
    "Doações",
    "Arrecadação e distribuição",
}

# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def coluna_presenca(subatividade: str) -> str | None:
    """
    Retorna o grupo_nome que representa presença para a subatividade.
    Retorna None quando a subatividade é específica (excluir da análise).

    Exemplos:
        coluna_presenca("Oficina")    → "Presenças"
        coluna_presenca("Consulta")   → "Pessoas atendidas"
        coluna_presenca("Hospedagem") → "Inscritos no dia"
        coluna_presenca("Doações")    → None
    """
    if subatividade in EQUIVALE_PESSOAS_ATENDIDAS:
        return "Pessoas atendidas"
    if subatividade in EQUIVALE_INSCRITOS_DIA:
        return "Inscritos no dia"
    if subatividade in ESPECIFICAS:
        return None
    return "Presenças"


def eh_especifica(subatividade: str) -> bool:
    """True quando a subatividade não possui mensurador equivalente a presença."""
    return subatividade in ESPECIFICAS


def filtrar_com_presenca(df, col: str = "modalidade_desc"):
    """
    Remove linhas de subatividades específicas de um DataFrame.
    Aplica as equivalências: Pessoas atendidas e Inscritos no dia → Presenças.

    Parâmetros
    ----------
    df  : DataFrame com coluna `col` (subatividade) e `grupo_nome`
    col : nome da coluna de subatividade (padrão: 'modalidade_desc')

    Retorna DataFrame filtrado com coluna `presencas` calculada.
    """
    df = df[~df[col].isin(ESPECIFICAS)].copy()

    def _grupo_presenca(row):
        col_p = coluna_presenca(row[col])
        return row["valor_mensurador"] if row["grupo_nome"] == col_p else None

    df["presencas"] = df.apply(_grupo_presenca, axis=1)
    return df
