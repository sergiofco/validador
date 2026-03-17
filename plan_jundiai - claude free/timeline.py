import pandas as pd
from dash import Dash, html, dcc, Input, Output, State, callback_context
import dash_calendar_timeline as dct
import datetime


# -------------------------
# carregar planilha
# -------------------------

df = pd.read_excel("proposta de itens para Calendario 2026 GERAL.xlsx")

df["data_inicial"] = pd.to_datetime(df["data_inicial"], dayfirst=True, errors="coerce")
df["data_final"] = pd.to_datetime(df["data_final"], dayfirst=True, errors="coerce")

df = df.dropna(subset=["data_inicial", "data_final"]).copy()
df = df[df["data_final"] >= df["data_inicial"]].copy()

# -------------------------
# normalizações úteis
# -------------------------

df["tipo_norm"] = df["tipo"].fillna("").astype(str).str.strip().str.lower()
df["impacto_norm"] = df["impacto"].fillna("").astype(str).str.strip().str.lower()
df["grupo_norm"] = df["grupo"].fillna("").astype(str).str.strip()

df["impacto_norm"] = df["impacto_norm"].replace({
    "medio": "médio"
})

# -------------------------
# ordem fixa dos macro-grupos
# -------------------------

ordem_macro = [
    "Programação Sesc Jundiaí",
    "Programação Sesc SP",
    "Parcerias institucionais",
    "Gestão de Pessoas",
    "Ações internas",
    "GTs",
    "Eventos externos ao Sesc",
    "Calendário"
]

ordem_macro_mapa = {macro: i for i, macro in enumerate(ordem_macro)}

if "ord_macro_grupo" not in df.columns:
    df["ord_macro_grupo"] = df["macro-grupo"].map(ordem_macro_mapa)

df["ord_macro_grupo"] = df["ord_macro_grupo"].fillna(999)

df = df.sort_values(["ord_macro_grupo", "data_inicial", "atividade"]).copy()

# -------------------------
# paleta impacto
# -------------------------

cores_impacto = {
    "baixo": "#f4c542",
    "médio": "#f28e2b",
    "alto": "#d62828"
}

# -------------------------
# cores dos macro-grupos
# -------------------------

paleta_macro = [
    "#6C8EAD",
    "#8E6CAD",
    "#6CAD8E",
    "#AD8E6C",
    "#B85C5C",
    "#5C8BB8",
    "#8BB85C",
    "#B88B5C"
]

cores_macro = {
    macro: paleta_macro[i % len(paleta_macro)]
    for i, macro in enumerate(ordem_macro)
}

# -------------------------
# listas para filtros
# -------------------------

macros_presentes = [m for m in ordem_macro if m in df["macro-grupo"].dropna().unique()]

opcoes_macro = [
    {"label": m, "value": m}
    for m in macros_presentes
]

equipes_series = pd.concat(
    [
        df["equipe1"].dropna().astype(str).str.strip(),
        df["equipe2"].dropna().astype(str).str.strip()
    ]
)

equipes_unicas = sorted([e for e in equipes_series.unique().tolist() if e])

opcoes_equipe = [
    {"label": e, "value": e}
    for e in equipes_unicas
]

opcoes_tipo = [
    {"label": "Todos", "value": "TODOS"},
    {"label": "Interno", "value": "interno"},
    {"label": "Externo", "value": "externo"},
]

opcoes_impacto = [
    {"label": "Todos", "value": "TODOS"},
    {"label": "Baixo", "value": "baixo"},
    {"label": "Médio", "value": "médio"},
    {"label": "Alto", "value": "alto"},
]

grupos_unicos = sorted([g for g in df["grupo_norm"].dropna().unique().tolist() if g])

opcoes_grupo = [
    {"label": g, "value": g}
    for g in grupos_unicos
]

# -------------------------
# ano e zoom padrão
# -------------------------

ANO_ATUAL = 2026

ZOOM_PADRAO = {
    "visible_time_start": int(pd.Timestamp("2026-01-01").timestamp() * 1000),
    "visible_time_end": int(pd.Timestamp("2026-12-31").timestamp() * 1000),
    "primary_unit": "month",
    "secondary_unit": "week",
    "primary_format": "MMM YYYY",
    "secondary_format": " "
}

hoje = datetime.date.today()
inicio_semana = hoje - datetime.timedelta(days=hoje.weekday())
fim_semana = inicio_semana + datetime.timedelta(days=6)

TS_INICIO_SEMANA = int(pd.Timestamp(inicio_semana).timestamp() * 1000)
TS_FIM_SEMANA = int(pd.Timestamp(fim_semana).timestamp() * 1000)

# -------------------------
# helpers
# -------------------------

def fmt_val(valor):
    if pd.isna(valor):
        return "-"
    valor = str(valor).strip()
    return valor if valor else "-"

def fmt_data(valor):
    if pd.isna(valor):
        return "-"
    return pd.to_datetime(valor).strftime("%d/%m/%Y")

# -------------------------
# função para montar timeline
# -------------------------

def montar_timeline(df_filtrado: pd.DataFrame):
    groups = []
    custom_groups_content = []
    items = []
    detalhes_items = {}

    group_seq = 0

    if df_filtrado.empty:
        return groups, custom_groups_content, items, detalhes_items

    macros_no_df = [m for m in ordem_macro if m in df_filtrado["macro-grupo"].unique()]

    for macro in macros_no_df:
        bloco = df_filtrado[df_filtrado["macro-grupo"] == macro].copy()

        if bloco.empty:
            continue

        header_id = f"header_{group_seq}"

        groups.append({
            "id": header_id,
            "title": macro.upper()
        })

        custom_groups_content.append(
            html.Div(
                macro.upper(),
                className="macro-header",
                style={
                    "background": cores_macro.get(macro, "#999999")
                }
            )
        )

        group_seq += 1

        for _, row in bloco.iterrows():
            gid = f"g_{group_seq}"

            groups.append({
                "id": gid,
                "title": row["atividade"]
            })

            custom_groups_content.append(
                html.Div(
                    row["atividade"],
                    className="atividade-label"
                )
            )

            impacto = str(row["impacto_norm"]).strip().lower()
            cor_barra = cores_impacto.get(impacto, "#cccccc")

            items.append({
                "id": gid,
                "group": gid,
                "title": "",
                "start_time": int(row["data_inicial"].timestamp() * 1000),
                "end_time": int(row["data_final"].timestamp() * 1000),
                "itemProps": {
                    "style": {
                        "background": cor_barra,
                        "color": "white",
                        "borderRadius": "6px",
                        "border": "none"
                    }
                }
            })

            detalhes_items[gid] = {
                "atividade": fmt_val(row.get("atividade")),
                "macro_grupo": fmt_val(row.get("macro-grupo")),
                "grupo": fmt_val(row.get("grupo")),
                "data_inicial": fmt_data(row.get("data_inicial")),
                "data_final": fmt_data(row.get("data_final")),
                "tipo": fmt_val(row.get("tipo")),
                "responsavel": fmt_val(row.get("responsavel")),
                "acesso": fmt_val(row.get("ACESSO À VISUALIZAÇÃO (público de interesse)")),
                "impacto": fmt_val(row.get("impacto")),
                "equipe1": fmt_val(row.get("equipe1")),
                "equipe2": fmt_val(row.get("equipe2"))
            }

            group_seq += 1

    return groups, custom_groups_content, items, detalhes_items

# -------------------------
# app
# -------------------------

app = Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div(
    [
        # ---- faixa vermelha: título + ano como link de reset ----
        html.Div(
            [
                html.Span(
                    "Sesc Jundiaí — Planejamento — ",
                    style={
                        "color": "white",
                        "fontFamily": "'Ubuntu', sans-serif",
                        "fontWeight": "700",
                        "fontSize": "22px",
                        "letterSpacing": "0.2px"
                    }
                ),
                html.A(
                    str(ANO_ATUAL),
                    id="btn_reset_zoom",
                    href="#",
                    title="Clique para voltar à visão anual",
                    style={
                        "color": "white",
                        "fontFamily": "'Ubuntu', sans-serif",
                        "fontWeight": "700",
                        "fontSize": "22px",
                        "textDecoration": "underline",
                        "textDecorationColor": "rgba(255,255,255,0.4)",
                        "letterSpacing": "0.2px",
                        "cursor": "pointer"
                    }
                ),
            ],
            style={
                "background": "#046b7e",
                "padding": "12px 20px",
                "display": "flex",
                "alignItems": "center",
                "gap": "0px"
            }
        ),

        # ---- barra de filtros (uma linha) ----
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Macro-grupo", className="filtro-label"),
                        dcc.Dropdown(
                            id="filtro_macro",
                            options=opcoes_macro,
                            value=[],
                            multi=True,
                            placeholder="Selecione macro-grupos"
                        ),
                    ],
                    className="filtro-bloco filtro-wide"
                ),
                html.Div(
                    [
                        html.Label("Equipe impactada", className="filtro-label"),
                        dcc.Dropdown(
                            id="filtro_equipe",
                            options=opcoes_equipe,
                            value=[],
                            multi=True,
                            placeholder="Selecione equipes"
                        ),
                    ],
                    className="filtro-bloco filtro-wide"
                ),
                html.Div(
                    [
                        html.Label("Tipo", className="filtro-label"),
                        dcc.Dropdown(
                            id="filtro_tipo",
                            options=opcoes_tipo,
                            value="TODOS",
                            multi=False,
                            clearable=False
                        ),
                    ],
                    className="filtro-bloco filtro-narrow"
                ),
                html.Div(
                    [
                        html.Label("Impacto", className="filtro-label"),
                        dcc.Dropdown(
                            id="filtro_impacto",
                            options=opcoes_impacto,
                            value="TODOS",
                            multi=False,
                            clearable=False
                        ),
                    ],
                    className="filtro-bloco filtro-narrow"
                ),
                html.Div(
                    [
                        html.Label("Grupo", className="filtro-label"),
                        dcc.Dropdown(
                            id="filtro_grupo",
                            options=opcoes_grupo,
                            value=[],
                            multi=True,
                            placeholder="Selecione grupos"
                        ),
                    ],
                    className="filtro-bloco filtro-wide"
                ),
                html.Div(
                    [
                        html.Label("\u00a0", className="filtro-label", style={"display": "block"}),
                        html.Button(
                            "✕  Limpar filtros",
                            id="btn_limpar_filtros",
                            n_clicks=0,
                            className="btn-limpar"
                        ),
                    ],
                    style={"display": "flex", "flexDirection": "column", "justifyContent": "flex-end", "flexShrink": "0"}
                ),
            ],
            style={
                "display": "flex",
                "gap": "12px",
                "alignItems": "flex-end",
                "flexWrap": "nowrap",
                "padding": "12px 20px",
                "background": "white",
                "borderBottom": "1px solid #e0e0e0",
                "boxShadow": "0 1px 4px rgba(0,0,0,0.06)",
                "overflowX": "auto"
            }
        ),

        dcc.Store(id="store_detalhes_items"),
        dcc.Store(id="store_zoom_config", data=ZOOM_PADRAO),

        html.Div(
            [
                html.Div(id="timeline_container", style={"flex": "1 1 auto", "minWidth": "900px"}),
                html.Div(
                    id="painel_detalhe",
                    style={
                        "width": "320px",
                        "minWidth": "320px",
                        "background": "#f7f7f7",
                        "borderRadius": "10px",
                        "padding": "16px",
                        "border": "1px solid #dddddd",
                        "height": "fit-content"
                    }
                )
            ],
            style={
                "display": "flex",
                "gap": "20px",
                "alignItems": "flex-start",
                "padding": "0 20px 20px 20px"
            }
        )
    ],
    style={"padding": "0", "background": "#f3f3f3", "minHeight": "100vh"}
)

# -------------------------
# callback: limpar filtros
# -------------------------

@app.callback(
    Output("filtro_macro", "value"),
    Output("filtro_equipe", "value"),
    Output("filtro_tipo", "value"),
    Output("filtro_impacto", "value"),
    Output("filtro_grupo", "value"),
    Input("btn_limpar_filtros", "n_clicks"),
    prevent_initial_call=True
)
def limpar_filtros(n_clicks):
    return [], [], "TODOS", "TODOS", []

# -------------------------
# callback: zoom + reset ao clicar no ano
# -------------------------

@app.callback(
    Output("store_zoom_config", "data"),
    Input("btn_reset_zoom", "n_clicks"),
    Input("timeline", "zoomData"),
    State("store_zoom_config", "data"),
    prevent_initial_call=True
)
def gerenciar_zoom(n_clicks_reset, zoom_data, zoom_atual):
    ctx = callback_context
    if not ctx.triggered:
        return zoom_atual

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "btn_reset_zoom":
        return ZOOM_PADRAO

    if not zoom_data:
        return zoom_atual

    visible_start = zoom_data.get("zoomVisibleTimeStart", zoom_atual["visible_time_start"])
    visible_end = zoom_data.get("zoomVisibleTimeEnd", zoom_atual["visible_time_end"])

    intervalo_ms = visible_end - visible_start
    intervalo_dias = intervalo_ms / (1000 * 60 * 60 * 24)

    if intervalo_dias > 45:
        primary_unit = "month"
        secondary_unit = "week"
        primary_format = "MMM YYYY"
        secondary_format = " "
    else:
        primary_unit = "week"
        secondary_unit = "day"
        primary_format = "[semana de] D [de] MMMM"
        secondary_format = "ddd D"

    return {
        "visible_time_start": visible_start,
        "visible_time_end": visible_end,
        "primary_unit": primary_unit,
        "secondary_unit": secondary_unit,
        "primary_format": primary_format,
        "secondary_format": secondary_format
    }

# -------------------------
# callback principal da timeline
# -------------------------

@app.callback(
    Output("timeline_container", "children"),
    Output("store_detalhes_items", "data"),
    Input("filtro_macro", "value"),
    Input("filtro_equipe", "value"),
    Input("filtro_tipo", "value"),
    Input("filtro_impacto", "value"),
    Input("filtro_grupo", "value"),
    Input("store_zoom_config", "data")
)
def atualizar_timeline(
    macros_selecionados,
    equipes_selecionadas,
    tipo_selecionado,
    impacto_selecionado,
    grupos_selecionados,
    zoom_config
):
    df_filtrado = df.copy()

    if macros_selecionados is None:
        macros_selecionados = []
    elif isinstance(macros_selecionados, str):
        macros_selecionados = [macros_selecionados]

    if equipes_selecionadas is None:
        equipes_selecionadas = []
    elif isinstance(equipes_selecionadas, str):
        equipes_selecionadas = [equipes_selecionadas]

    if grupos_selecionados is None:
        grupos_selecionados = []
    elif isinstance(grupos_selecionados, str):
        grupos_selecionados = [grupos_selecionados]

    if macros_selecionados:
        df_filtrado = df_filtrado[df_filtrado["macro-grupo"].isin(macros_selecionados)]

    if equipes_selecionadas:
        equipes_selecionadas = [str(e).strip() for e in equipes_selecionadas]
        mask_equipe1 = df_filtrado["equipe1"].fillna("").astype(str).str.strip().isin(equipes_selecionadas)
        mask_equipe2 = df_filtrado["equipe2"].fillna("").astype(str).str.strip().isin(equipes_selecionadas)
        df_filtrado = df_filtrado[mask_equipe1 | mask_equipe2]

    if tipo_selecionado and tipo_selecionado != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["tipo_norm"] == tipo_selecionado]

    if impacto_selecionado and impacto_selecionado != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["impacto_norm"] == impacto_selecionado]

    if grupos_selecionados:
        grupos_selecionados = [str(g).strip() for g in grupos_selecionados]
        df_filtrado = df_filtrado[df_filtrado["grupo_norm"].isin(grupos_selecionados)]

    df_filtrado = df_filtrado.sort_values(["ord_macro_grupo", "data_inicial", "atividade"]).copy()

    groups, custom_groups_content, items, detalhes_items = montar_timeline(df_filtrado)

    if not items:
        return (
            html.Div(
                "Nenhuma atividade encontrada para os filtros selecionados.",
                style={
                    "padding": "20px",
                    "background": "#f5f5f5",
                    "borderRadius": "8px",
                    "color": "#444"
                }
            ),
            {}
        )

    timeline = dct.DashCalendarTimeline(
        id="timeline",
        groups=groups,
        items=items,
        sidebarHeaderContent=html.Div(style={"background": "#046b7e", "height": "100%"}),
        defaultTimeStart=int(pd.Timestamp("2026-01-01").timestamp() * 1000),
        defaultTimeEnd=int(pd.Timestamp("2026-12-31").timestamp() * 1000),
        visibleTimeStart=zoom_config["visible_time_start"],
        visibleTimeEnd=zoom_config["visible_time_end"],
        primaryDateHeaderUnit=zoom_config["primary_unit"],
        secondaryDateHeaderUnit=zoom_config["secondary_unit"],
        primaryDateHeaderLabelFormat=zoom_config["primary_format"],
        secondaryDateHeaderLabelFormat=zoom_config["secondary_format"],
        minZoom=24 * 60 * 60 * 1000,
        maxZoom=365 * 24 * 60 * 60 * 1000,
        buffer=1,
        sidebarWidth=380,
        lineHeight=35,
        itemHeightRatio=0.72,
        customGroups=True,
        customGroupsContent=custom_groups_content,
        groupsStyle={
            "display": "flex",
            "alignItems": "center",
            "minHeight": "35px"
        },
        customMarkers=[
            {"date": TS_INICIO_SEMANA, "style": {"backgroundColor": "#c47004", "width": "2px"}},
            {"date": TS_FIM_SEMANA,    "style": {"backgroundColor": "#c47004", "width": "2px"}},
        ],
        showTodayMarker=True,
        todayMarkerStyle={"backgroundColor": "#c47004", "width": "2px"},
    )

    return timeline, detalhes_items

# -------------------------
# callback do painel de detalhe
# -------------------------

@app.callback(
    Output("painel_detalhe", "children"),
    Input("timeline", "itemSelectData"),
    State("store_detalhes_items", "data")
)
def mostrar_detalhe(item_select_data, detalhes_items):
    if not item_select_data or not detalhes_items:
        return html.Div(
            [
                html.Div("Detalhes da atividade", style={"fontWeight": "700", "fontSize": "16px", "marginBottom": "10px"}),
                html.Div("Clique em uma barra da timeline para ver as informações.", style={"fontSize": "13px", "color": "#555"})
            ]
        )

    item_id = item_select_data.get("itemId")
    detalhe = detalhes_items.get(item_id)

    if not detalhe:
        return html.Div("Selecione uma atividade válida.")

    return html.Div(
        [
            html.Div(detalhe["atividade"], style={"fontWeight": "700", "fontSize": "11px", "marginBottom": "6px"}),
            html.Div(detalhe["macro_grupo"], style={"fontSize": "9px", "marginBottom": "2px", "color": "#444"}),
            html.Div(detalhe["grupo"], style={"fontSize": "9px", "marginBottom": "8px", "color": "#444"}),
            html.Div(f"de {detalhe['data_inicial']} até {detalhe['data_final']}", style={"fontSize": "12px", "marginBottom": "10px"}),
            html.Div(f"tipo: {detalhe['tipo']}", style={"fontSize": "12px", "marginBottom": "4px"}),
            html.Div(f"responsável: {detalhe['responsavel']}", style={"fontSize": "12px", "marginBottom": "4px"}),
            html.Div(f"acesso à visualização: {detalhe['acesso']}", style={"fontSize": "12px", "marginBottom": "4px"}),
            html.Div(f"impacto: {detalhe['impacto']}", style={"fontSize": "12px", "marginBottom": "4px"}),
            html.Div(f"equipe1: {detalhe['equipe1']}", style={"fontSize": "12px", "marginBottom": "4px"}),
            html.Div(f"equipe2: {detalhe['equipe2']}", style={"fontSize": "12px", "marginBottom": "4px"}),
        ]
    )

if __name__ == "__main__":
    app.run(debug=True)
