"""
Saude+ Analytics+ Dashboard
Case Técnico – Time de Dados
"""

import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Saude+ Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Color palette
COLORS = {
    "primary": "#411e6f",
    "secondary": "#f3b5be",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "neutral": "#000000",
}

# Medication class colors (consistent across all charts)
MED_CLASS_COLORS = {
    "Controle Especial": "#411e6f",  # primary
    "Antibióticos": "#f3b5be",      # secondary
    "MIP (Sem Receita)": "#7c3aed", # purple-600 from palette
}

PALETTE = [
    "#411e6f", "#f3b5be", "#ffffff", "#000000", "#7c3aed", "#fb7185",
]

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@st.cache_data(show_spinner="Carregando dados…")
def load_data():
    df = pd.read_csv(os.path.join(DATA_DIR, "prescricaomedicamento.csv"))
    med = pd.read_csv(os.path.join(DATA_DIR, "medicamentos.csv"))
    doc = pd.read_csv(os.path.join(DATA_DIR, "medicos.csv"))

    # ── clean prescricao ──
    df["dataprescricao"] = pd.to_datetime(df["dataprescricao"])
    df["datavenda"] = pd.to_datetime(df["datavenda"], errors="coerce")
    df["data"] = df["dataprescricao"].dt.date
    df["semana"] = df["dataprescricao"].dt.to_period("W").dt.start_time
    df["mes"] = df["dataprescricao"].dt.to_period("M").dt.start_time
    df["dia_semana"] = df["dataprescricao"].dt.day_name()

    # normalise sexo
    df["sexopaciente"] = df["sexopaciente"].replace(
        {"F": "Feminino", "M": "Masculino", "1": "NaoInformado", "0": "NaoInformado"}
    )

    # merge
    df = df.merge(doc[["idmedico", "especialidade", "estado", "genero", "idade"]],
                  on="idmedico", how="left", suffixes=("_pac", "_med"))
    df = df.merge(med[["idmedicamento", "nome", "antimicrobiano", "controleespecial", "mip"]],
                  on="idmedicamento", how="left")

    return df, med, doc


def apply_date_filter(df: pd.DataFrame, date_range):
    if isinstance(date_range, tuple) and len(date_range) == 2 and date_range[0] and date_range[1]:
        start_date, end_date = date_range
        mask = (
            (df["dataprescricao"].dt.date >= start_date)
            & (df["dataprescricao"].dt.date <= end_date)
        )
        return df.loc[mask].copy()
    return df.copy()


df, med, doc = load_data()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    logo_path = os.path.join(os.path.dirname(__file__), "saudemais.png")
    st.image(logo_path, width=72)
    st.title("Saude+ Analytics")
    st.caption("Case Técnico — Time de Dados")
    st.divider()

    page = st.radio(
        "Navegação",
        [
            "📊 Overview",
            "👨‍⚕️ Médicos & Especialidades",
            "💊 Medicamentos",
            "📬 Open Rate & Conversão",
            "🔍 Insights Adicionais",
            "📈 Descrição de Métricas",
            "🔧 Build It Up",
            "🤖 Agente IA",
        ],
    )

    st.divider()

    # Date filter
    min_date = df["dataprescricao"].min().date()
    max_date = df["dataprescricao"].max().date()
    default_start = max_date - pd.Timedelta(days=30)
    if default_start < min_date:
        default_start = min_date
    date_range = st.date_input(
        "Período",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
        key="date_range",
    )
    dff = apply_date_filter(df, date_range)

    st.caption(f"**{len(dff):,}** linhas | **{dff['idprescricao'].nunique():,}** prescrições")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def kpi(label, value, delta=None, color=COLORS["primary"]):
    with st.container():
        if delta:
            st.metric(label, value, delta)
        else:
            st.metric(label, value)


def section(title, subtitle=""):
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)


# ─────────────────────────────────────────────
# PAGE: OVERVIEW
# ─────────────────────────────────────────────
if page == "📊 Overview":
    section("📊 Overview Geral", "Visão consolidada do período analisado")

    # ── KPIs ──
    total_presc = dff["idprescricao"].nunique()
    total_pacs = dff["idpaciente"].nunique()
    total_med = dff["idmedico"].nunique()
    media_diaria = dff.groupby("data")["idprescricao"].nunique().mean()
    open_rate = dff.groupby("idprescricao")["visualizadapaciente"].max().mean()
    conv_rate = (
        dff[dff["visualizadapaciente"]]
        .groupby("idprescricao")["itemvendido"]
        .max()
        .apply(lambda x: x > 0)
        .mean()
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Prescrições", f"{total_presc:,}")
    c2.metric("Pacientes Únicos", f"{total_pacs:,}")
    c3.metric("Médicos Ativos", f"{total_med:,}")
    c4.metric("Média Diária", f"{media_diaria:.0f}")
    c5.metric("Open Rate", f"{open_rate:.1%}")
    c6.metric("Conversão", f"{conv_rate:.1%}")

    st.divider()

    # ── Q1: Prescrições diárias + sazonalidade ──
    st.markdown("### Q1 · Prescrições diárias e sazonalidade")

    daily = dff.groupby("data")["idprescricao"].nunique().reset_index()
    daily.columns = ["data", "prescricoes"]
    daily["data"] = pd.to_datetime(daily["data"])

    # rolling 7d
    daily["media_7d"] = daily["prescricoes"].rolling(7, center=True).mean()

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=daily["data"], y=daily["prescricoes"],
        name="Prescrições", marker_color=COLORS["primary"], opacity=0.6
    ))
    fig1.add_trace(go.Scatter(
        x=daily["data"], y=daily["media_7d"],
        name="Média 7 dias", line=dict(color=COLORS["warning"], width=2.5)
    ))
    fig1.update_layout(
        height=340, legend=dict(orientation="h"),
        xaxis_title="Data", yaxis_title="Nº de Prescrições",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig1, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Por dia da semana**")
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_pt = {"Monday": "Seg", "Tuesday": "Ter", "Wednesday": "Qua",
                  "Thursday": "Qui", "Friday": "Sex", "Saturday": "Sáb", "Sunday": "Dom"}
        dow = dff.groupby("dia_semana")["idprescricao"].nunique().reindex(dow_order).reset_index()
        dow.columns = ["dia", "prescricoes"]
        dow["dia_pt"] = dow["dia"].map(dow_pt)
        fig_dow = px.bar(dow, x="dia_pt", y="prescricoes",
                         color="prescricoes", color_continuous_scale="Blues",
                         labels={"dia_pt": "Dia", "prescricoes": "Prescrições"})
        fig_dow.update_layout(height=260, showlegend=False,
                               coloraxis_showscale=False,
                               plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_dow, use_container_width=True)

    with col2:
        st.markdown("**Por hora do dia**")
        dff["hora"] = dff["dataprescricao"].dt.hour
        hour_df = dff.groupby("hora")["idprescricao"].nunique().reset_index()
        hour_df.columns = ["hora", "prescricoes"]
        fig_h = px.bar(hour_df, x="hora", y="prescricoes",
                       color="prescricoes", color_continuous_scale="Purples",
                       labels={"hora": "Hora", "prescricoes": "Prescrições"})
        fig_h.update_layout(height=260, showlegend=False,
                              coloraxis_showscale=False,
                              plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_h, use_container_width=True)

    # ── Q2: Pacientes ──
    st.divider()
    st.markdown("### Q2 · Pacientes atendidos")

    col1, col2 = st.columns(2)
    with col1:
        sexo = dff.drop_duplicates("idpaciente")["sexopaciente"].value_counts().reset_index()
        sexo.columns = ["Sexo", "Pacientes"]
        fig_sex = px.pie(sexo, names="Sexo", values="Pacientes",
                         color_discrete_sequence=PALETTE, hole=0.45)
        fig_sex.update_layout(height=280, title="Distribuição por Sexo",
                               paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_sex, use_container_width=True)

    with col2:
        estado = dff.drop_duplicates("idpaciente")["estadopaciente"].value_counts().head(10).reset_index()
        estado.columns = ["Estado", "Pacientes"]
        fig_est = px.bar(estado, x="Pacientes", y="Estado", orientation="h",
                         color="Pacientes", color_continuous_scale="Teal",
                         labels={"Estado": "", "Pacientes": "Pacientes"})
        fig_est.update_layout(height=280, title="Top 10 Estados",
                               yaxis={"categoryorder": "total ascending"},
                               coloraxis_showscale=False,
                               plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_est, use_container_width=True)


# ─────────────────────────────────────────────
# PAGE: MÉDICOS
# ─────────────────────────────────────────────
elif page == "👨‍⚕️ Médicos & Especialidades":
    section("👨‍⚕️ Médicos & Especialidades", "Q3 · Quais especialidades mais prescreveram?")

    # Q3
    esp = (
        dff.groupby("especialidade")["idprescricao"]
        .nunique()
        .reset_index()
        .sort_values("idprescricao", ascending=False)
        .head(15)
    )
    esp.columns = ["Especialidade", "Prescrições"]

    fig_esp = px.bar(
        esp, x="Prescrições", y="Especialidade", orientation="h",
        color="Prescrições", color_continuous_scale="Blues",
    )
    fig_esp.update_layout(
        height=480, yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_esp, use_container_width=True)

    st.divider()
    st.markdown("### Conversão por Especialidade (Top 10)")

    esp_conv = (
        dff.groupby("especialidade")
        .agg(
            prescricoes=("idprescricao", "nunique"),
            abertas=("visualizadapaciente", "max"),
        )
    )
    # correctly compute open per prescription
    presc_open = dff.groupby(["idprescricao", "especialidade"])["visualizadapaciente"].max().reset_index()
    presc_sold = dff.groupby(["idprescricao", "especialidade"])["itemvendido"].max().reset_index()
    presc_sold["vendido"] = presc_sold["itemvendido"] > 0
    merged_esp = presc_open.merge(presc_sold, on=["idprescricao", "especialidade"])
    esp_stats = merged_esp.groupby("especialidade").agg(
        total=("idprescricao", "count"),
        abertas=("visualizadapaciente", "sum"),
        vendidas=("vendido", "sum"),
    ).reset_index()
    esp_stats["open_rate"] = esp_stats["abertas"] / esp_stats["total"]
    esp_stats["conv_rate"] = esp_stats["vendidas"] / esp_stats["abertas"].replace(0, 1)
    esp_stats = esp_stats[esp_stats["total"] >= 50].sort_values("total", ascending=False).head(10)

    fig_rates = go.Figure()
    fig_rates.add_trace(go.Bar(
        name="Open Rate", x=esp_stats["especialidade"],
        y=esp_stats["open_rate"], marker_color=COLORS["primary"],
        text=esp_stats["open_rate"].map("{:.1%}".format), textposition="outside",
    ))
    fig_rates.add_trace(go.Bar(
        name="Conversão", x=esp_stats["especialidade"],
        y=esp_stats["conv_rate"], marker_color=COLORS["success"],
        text=esp_stats["conv_rate"].map("{:.1%}".format), textposition="outside",
    ))
    fig_rates.update_layout(
        barmode="group", height=400, yaxis_tickformat=".0%",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_rates, use_container_width=True)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Distribuição por Conselho Profissional**")
        # Análise de Conselho Profissional (CRO vs CRM)
        conselho_counts = doc['conselhoprofissional'].value_counts(dropna=False)
        conselho_pct = (conselho_counts / len(doc) * 100).round(2)

        conselho_labels = {
            'CRM': 'CRM - Conselho Regional de Medicina',
            'CRO': 'CRO - Conselho Regional de Odontologia',
            'CRMV': 'CRMV - Conselho Regional de Medicina Veterinária'
        }

        conselho_data = []
        for conselho, count in conselho_counts.items():
            label = conselho_labels.get(str(conselho), str(conselho) if pd.notna(conselho) else "Não informado")
            conselho_data.append({'Conselho': label, 'Médicos': count, 'Percentual': conselho_pct[conselho]})

        conselho_df = pd.DataFrame(conselho_data)

        fig_conselho = px.bar(
            conselho_df, x="Conselho", y="Médicos",
            color="Percentual", color_continuous_scale="Blues",
            text=conselho_df["Percentual"].map("{:.1f}%".format)
        )
        fig_conselho.update_layout(
            height=260, xaxis_title="Conselho Profissional", yaxis_title="Médicos",
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_conselho, use_container_width=True)

    with col2:
        st.markdown("**Gênero dos Médicos**")
        gen_doc = doc["genero"].value_counts().reset_index()
        gen_doc.columns = ["Gênero", "Médicos"]
        fig_gen = px.pie(gen_doc, names="Gênero", values="Médicos",
                         color_discrete_sequence=PALETTE, hole=0.45)
        fig_gen.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gen, use_container_width=True)


# ─────────────────────────────────────────────
# PAGE: MEDICAMENTOS
# ─────────────────────────────────────────────
elif page == "💊 Medicamentos":
    section("💊 Medicamentos", "Análise dos medicamentos prescritos")

    top_med = (
        dff.groupby("nome")["idprescricao"]
        .nunique()
        .reset_index()
        .sort_values("idprescricao", ascending=False)
        .head(20)
    )
    top_med.columns = ["Medicamento", "Prescrições"]

    fig_med = px.bar(
        top_med, x="Prescrições", y="Medicamento", orientation="h",
        color="Prescrições", color_continuous_scale="Teal",
    )
    fig_med.update_layout(
        height=560, yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_med, use_container_width=True)

    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Antibióticos**")
        anti = dff.groupby("antimicrobiano")["idprescricao"].nunique().reset_index()
        anti["antimicrobiano"] = anti["antimicrobiano"].map({True: "Sim", False: "Não"})
        anti.columns = ["Antimicrobiano", "Prescrições"]
        fig_a = px.pie(anti, names="Antimicrobiano", values="Prescrições",
                       color_discrete_sequence=[COLORS["danger"], COLORS["neutral"]], hole=0.5)
        fig_a.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_a, use_container_width=True)

    with col2:
        st.markdown("**Controle Especial**")
        ctrl = dff.groupby("controleespecial")["idprescricao"].nunique().reset_index()
        ctrl["controleespecial"] = ctrl["controleespecial"].map({True: "Sim", False: "Não"})
        ctrl.columns = ["Controle Especial", "Prescrições"]
        fig_c = px.pie(ctrl, names="Controle Especial", values="Prescrições",
                       color_discrete_sequence=[COLORS["warning"], COLORS["neutral"]], hole=0.5)
        fig_c.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_c, use_container_width=True)

    with col3:
        st.markdown("**MIP (Sem Receita)**")
        mip_d = dff.groupby("mip")["idprescricao"].nunique().reset_index()
        mip_d["mip"] = mip_d["mip"].map({True: "Sim", False: "Não"})
        mip_d.columns = ["MIP", "Prescrições"]
        fig_m = px.pie(mip_d, names="MIP", values="Prescrições",
                       color_discrete_sequence=[COLORS["success"], COLORS["neutral"]], hole=0.5)
        fig_m.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_m, use_container_width=True)

    st.divider()
    st.markdown("### Taxa de Conversão por Medicamento (Top 15 mais prescritos)")
    med_conv = (
        dff.groupby("nome")
        .agg(
            prescricoes=("idprescricao", "nunique"),
            vendidos=("itemvendido", lambda x: (x > 0).sum()),
            abertas=("visualizadapaciente", "sum"),
        )
        .reset_index()
    )
    med_conv["conv"] = med_conv["vendidos"] / med_conv["abertas"].replace(0, 1)
    top15 = med_conv.nlargest(15, "prescricoes")

    fig_mc = px.scatter(
        top15, x="prescricoes", y="conv",
        size="vendidos", color="conv",
        text="nome",
        color_continuous_scale="RdYlGn",
        labels={"prescricoes": "Nº Prescrições", "conv": "Taxa de Conversão"},
    )
    fig_mc.update_traces(textposition="top center", textfont_size=9)
    fig_mc.update_layout(height=420, yaxis_tickformat=".0%",
                          coloraxis_showscale=False,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_mc, use_container_width=True)

    st.divider()
    st.markdown("### Taxa de Conversão por Dia — Classes de Medicamentos")

    presc_daily = (
        dff.groupby("idprescricao")
        .agg(
            dataprescricao=("dataprescricao", "min"),
            datavenda=("datavenda", "min"),
            visualizada=("visualizadapaciente", "max"),
            vendido=("itemvendido", lambda x: (x > 0).any()),
            controleespecial=("controleespecial", "max"),
            antimicrobiano=("antimicrobiano", "max"),
            mip=("mip", "max"),
        )
        .reset_index()
    )
    presc_daily["data"] = presc_daily["dataprescricao"].dt.date
    presc_daily["tempo_dias"] = (
        (presc_daily["datavenda"] - presc_daily["dataprescricao"]) .dt.total_seconds() / 86400
    )

    def make_daily_conversion(flag_col, title, color):
        temp = presc_daily[presc_daily[flag_col]].copy()
        daily = temp.groupby("data").agg(
            prescricoes=("idprescricao", "nunique"),
            abertas=("visualizada", "sum"),
            vendidas=("vendido", "sum"),
        ).reset_index()
        daily["conv_rate"] = daily["vendidas"] / daily["abertas"].replace(0, 1)
        fig = px.line(
            daily, x="data", y="conv_rate", markers=True,
            title=title, color_discrete_sequence=[color],
        )
        fig.update_layout(
            height=300, yaxis_tickformat=".0%",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    col1, col2, col3 = st.columns(3)
    with col1:
        st.plotly_chart(
            make_daily_conversion("controleespecial", "Controle Especial", MED_CLASS_COLORS["Controle Especial"]),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            make_daily_conversion("antimicrobiano", "Antibióticos", MED_CLASS_COLORS["Antibióticos"]),
            use_container_width=True,
        )
    with col3:
        st.plotly_chart(
            make_daily_conversion("mip", "MIP (Sem Receita)", MED_CLASS_COLORS["MIP (Sem Receita)"]),
            use_container_width=True,
        )

    st.divider()
    st.markdown("### Conversão por Janela de Tempo (1d / 2-7d / 8-15d)")

    sold_windows = presc_daily[presc_daily["vendido"] & presc_daily["datavenda"].notna()].copy()

    def classify_window(days):
        if days <= 1:
            return "1 dia"
        if days <= 7:
            return "2-7 dias"
        if days <= 15:
            return "8-15 dias"
        return ">15 dias"

    sold_windows["janela"] = sold_windows["tempo_dias"].apply(classify_window)
    window_rows = []
    class_map = [
        ("controleespecial", "Controle Especial", MED_CLASS_COLORS["Controle Especial"]),
        ("antimicrobiano", "Antibióticos", MED_CLASS_COLORS["Antibióticos"]),
        ("mip", "MIP (Sem Receita)", MED_CLASS_COLORS["MIP (Sem Receita)"]),
    ]
    for flag_col, label, _ in class_map:
        class_df = sold_windows[sold_windows[flag_col]].copy()
        total = len(class_df)
        if total == 0:
            continue
        counts = (
            class_df.groupby("janela")["idprescricao"]
            .nunique()
            .reset_index(name="vendas")
        )
        counts["classe"] = label
        counts["pct_vendas"] = counts["vendas"] / total
        window_rows.append(counts)

    if window_rows:
        window_df = pd.concat(window_rows, ignore_index=True)
        window_df["janela"] = pd.Categorical(
            window_df["janela"],
            categories=["1 dia", "2-7 dias", "8-15 dias", ">15 dias"],
            ordered=True,
        )
        window_df = window_df.sort_values(["classe", "janela"])
        fig_window = px.bar(
            window_df, x="janela", y="pct_vendas", color="classe",
            barmode="group", text=window_df["pct_vendas"].map("{:.1%}".format),
            labels={"janela": "Janela", "pct_vendas": "Participação das Vendas", "classe": "Classe"},
        )
        fig_window.update_layout(
            height=380, yaxis_tickformat=".0%",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_window, use_container_width=True)
    else:
        st.info("Não há vendas classificadas por janela de tempo no período selecionado.")

    st.divider()
    st.markdown("### Vendas Diárias por Canal e Classe de Medicamento")

    # Marketplace sales by day and class
    marketplace_sales = dff[
        (dff["canalvenda"] == "marketplace") & (dff["itemvendido"] > 0)
    ].copy()

    # Physical sales by day and class
    physical_sales = dff[
        (dff["canalvenda"] == "farmacia fisica") & (dff["itemvendido"] > 0)
    ].copy()

    def daily_sales_by_class(df, title, color):
        daily_class_sales = []
        for flag_col, label in [
            ("controleespecial", "Controle Especial"),
            ("antimicrobiano", "Antibióticos"),
            ("mip", "MIP (Sem Receita)"),
        ]:
            class_data = df[df[flag_col]].groupby("data")["idprescricao"].nunique().reset_index()
            class_data["Classe"] = label
            class_data = class_data.rename(columns={"idprescricao": "Vendas"})
            daily_class_sales.append(class_data)

        if daily_class_sales:
            daily_df = pd.concat(daily_class_sales, ignore_index=True)
            fig = px.line(
                daily_df, x="data", y="Vendas", color="Classe",
                title=title, markers=True,
                color_discrete_map=MED_CLASS_COLORS,
            )
            fig.update_layout(
                height=350,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            return fig
        return None

    col1, col2 = st.columns(2)
    with col1:
        marketplace_fig = daily_sales_by_class(marketplace_sales, "Vendas Diárias no Marketplace", COLORS["primary"])
        if marketplace_fig:
            st.plotly_chart(marketplace_fig, use_container_width=True)
        else:
            st.info("Não há vendas no marketplace no período selecionado.")

    with col2:
        physical_fig = daily_sales_by_class(physical_sales, "Vendas Diárias na Farmácia Física", COLORS["secondary"])
        if physical_fig:
            st.plotly_chart(physical_fig, use_container_width=True)
        else:
            st.info("Não há vendas na farmácia física no período selecionado.")


# ─────────────────────────────────────────────
# PAGE: OPEN RATE & CONVERSÃO
# ─────────────────────────────────────────────
elif page == "📬 Open Rate & Conversão":
    section("📬 Open Rate & Conversão", "Q4 · Open Rate | Q5 · Conversão por canal")

    # per-prescription level
    presc_level = (
        dff.groupby("idprescricao")
        .agg(
            visualizada=("visualizadapaciente", "max"),
            vendido=("itemvendido", lambda x: (x > 0).any()),
            canal=("canalvenda", lambda x: x[x != "não convertido"].max()
                   if (x != "não convertido").any() else "não convertido"),
        )
        .reset_index()
    )

    total_presc = len(presc_level)
    abertas = presc_level["visualizada"].sum()
    vendidas = presc_level["vendido"].sum()
    open_rate = abertas / total_presc
    conv_rate = vendidas / abertas if abertas > 0 else 0

    st.markdown("### Funil de Engajamento")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Prescrições", f"{total_presc:,}")
    col2.metric("Visualizadas (Open Rate)", f"{abertas:,}", f"{open_rate:.1%}")
    col3.metric("Vendas (Conversão)", f"{vendidas:,}", f"{conv_rate:.1%}")

    # Funnel chart
    fig_funnel = go.Figure(go.Funnel(
        y=["Prescrições Emitidas", "Receitas Abertas", "Vendas Realizadas"],
        x=[total_presc, abertas, vendidas],
        textinfo="value+percent initial",
        marker_color=[COLORS["primary"], COLORS["warning"], COLORS["success"]],
    ))
    fig_funnel.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_funnel, use_container_width=True)

    st.divider()

    # Análise por Convênio
    st.markdown("### 📊 Estatísticas de Convênios")

    convenio_stats = dff.groupby("idconvenio")["idprescricao"].nunique().reset_index()
    convenio_stats.columns = ["Convênio", "Prescrições"]

    total_prescricoes = convenio_stats["Prescrições"].sum()
    com_convenio = convenio_stats[convenio_stats["Convênio"].notna()]["Prescrições"].sum()
    sem_convenio = convenio_stats[convenio_stats["Convênio"].isna()]["Prescrições"].sum()
    distinct_convenios = convenio_stats["Convênio"].notna().sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Prescrições", f"{total_prescricoes:,}")
    col2.metric("Com Convênio", f"{com_convenio:,}", f"{com_convenio/total_prescricoes:.1%}")
    col3.metric("Sem Convênio (Particular)", f"{sem_convenio:,}", f"{sem_convenio/total_prescricoes:.1%}")
    col4.metric("Convênios Distintos", f"{distinct_convenios:,}")

    # Top convênios
    top_convenios = convenio_stats[convenio_stats["Convênio"].notna()].sort_values("Prescrições", ascending=False).head(10)
    top_convenios["Convênio"] = top_convenios["Convênio"].astype(int).astype(str)
    top_convenios["Convênio"] = "Convênio " + top_convenios["Convênio"]

    fig_convenios = px.bar(
        top_convenios, x="Prescrições", y="Convênio", orientation="h",
        color="Prescrições", color_continuous_scale="Greens",
        text=top_convenios["Prescrições"].map("{:,}".format)
    )
    fig_convenios.update_layout(
        height=400, yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        title="Top 10 Convênios por Volume de Prescrições"
    )
    st.plotly_chart(fig_convenios, use_container_width=True)

    st.divider()

    # Q5: Conversão por canal
    st.markdown("### Q5 · Conversão por Canal de Venda")

    canal_df = (
        dff[dff["canalvenda"] != "não convertido"]
        .groupby("canalvenda")["idprescricao"]
        .nunique()
        .reset_index()
    )
    canal_df.columns = ["Canal", "Vendas"]
    canal_df["% do Total"] = canal_df["Vendas"] / canal_df["Vendas"].sum()

    col1, col2 = st.columns([1, 1])
    with col1:
        fig_canal = px.pie(
            canal_df, names="Canal", values="Vendas",
            color_discrete_sequence=[COLORS["primary"], COLORS["success"]],
            hole=0.5,
        )
        fig_canal.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_canal, use_container_width=True)

    with col2:
        # Conversão por canal ao longo do tempo
        canal_time = (
            dff[dff["canalvenda"] != "não convertido"]
            .groupby(["semana", "canalvenda"])["idprescricao"]
            .nunique()
            .reset_index()
        )
        canal_time.columns = ["Semana", "Canal", "Vendas"]
        fig_ct = px.line(
            canal_time, x="Semana", y="Vendas", color="Canal",
            color_discrete_sequence=[COLORS["primary"], COLORS["success"]],
            markers=True,
        )
        fig_ct.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)",
                               legend=dict(orientation="h"))
        st.plotly_chart(fig_ct, use_container_width=True)

    # Conversão por canal detalhada
    st.markdown("### Conversão por Canal (Visualizadas → Vendidas)")
    canal_conv = (
        dff.groupby("canalvenda")["idprescricao"]
        .nunique()
        .reset_index()
    )
    canal_conv.columns = ["Canal", "Prescrições"]

    # open rate over time
    st.divider()
    st.markdown("### Open Rate Semanal")

    weekly_open = (
        dff.groupby(["semana", "idprescricao"])["visualizadapaciente"]
        .max()
        .reset_index()
        .groupby("semana")["visualizadapaciente"]
        .mean()
        .reset_index()
    )
    weekly_open.columns = ["Semana", "Open Rate"]

    fig_or = px.line(
        weekly_open, x="Semana", y="Open Rate",
        markers=True, color_discrete_sequence=[COLORS["primary"]],
    )
    fig_or.update_layout(
        height=300, yaxis_tickformat=".0%",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    fig_or.add_hline(y=weekly_open["Open Rate"].mean(),
                      line_dash="dash", line_color=COLORS["warning"],
                      annotation_text=f"Média {weekly_open['Open Rate'].mean():.1%}")
    st.plotly_chart(fig_or, use_container_width=True)

    # Open rate por dia da semana
    st.markdown("### Open Rate por Dia da Semana de Envio")
    dow_open = (
        dff.groupby(["dia_semana", "idprescricao"])["visualizadapaciente"]
        .max()
        .reset_index()
        .groupby("dia_semana")["visualizadapaciente"]
        .mean()
        .reset_index()
    )
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_pt = {"Monday": "Seg", "Tuesday": "Ter", "Wednesday": "Qua",
              "Thursday": "Qui", "Friday": "Sex", "Saturday": "Sáb", "Sunday": "Dom"}
    dow_open["dia_semana"] = pd.Categorical(dow_open["dia_semana"], categories=dow_order, ordered=True)
    dow_open = dow_open.sort_values("dia_semana")
    dow_open["dia_pt"] = dow_open["dia_semana"].map(dow_pt)

    fig_dow_or = px.bar(
        dow_open, x="dia_pt", y="visualizadapaciente",
        color="visualizadapaciente", color_continuous_scale="Blues",
        text=dow_open["visualizadapaciente"].map("{:.1%}".format),
        labels={"dia_pt": "Dia", "visualizadapaciente": "Open Rate"},
    )
    fig_dow_or.update_layout(height=300, yaxis_tickformat=".0%",
                               coloraxis_showscale=False,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_dow_or, use_container_width=True)


# ─────────────────────────────────────────────
# PAGE: INSIGHTS ADICIONAIS
# ─────────────────────────────────────────────
elif page == "🔍 Insights Adicionais":
    section("🔍 Insights Adicionais", "Q6 & Q7 · Outras análises e oportunidades de melhoria")

    st.markdown("### ⏱️ Tempo de Venda: Marketplace vs Farmácia Física")

    # Filtrar apenas vendas realizadas
    vendas = dff[dff["itemvendido"] == True].copy()
    vendas["tempo_horas"] = (vendas["datavenda"] - vendas["dataprescricao"]).dt.total_seconds() / 3600
    vendas["tempo_dias"] = vendas["tempo_horas"] / 24
    vendas = vendas[vendas["tempo_horas"] >= 0]

    # Separar por canal
    marketplace = vendas[vendas["canalvenda"] == "marketplace"]
    farmacia_fisica = vendas[vendas["canalvenda"] == "farmacia fisica"]

    # Estatísticas gerais
    total_vendas = len(vendas)
    tempo_medio_geral = vendas["tempo_horas"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Vendas", f"{total_vendas:,}")
    col2.metric("Tempo Médio Geral", f"{tempo_medio_geral:.1f}h")
    col3.metric("Mediana Geral", f"{vendas['tempo_horas'].median():.1f}h")

    # Comparação entre canais
    st.markdown("#### 📊 Comparação: Marketplace vs Farmácia Física")

    canal_comparison = pd.DataFrame({
        'Canal': ['Marketplace', 'Farmácia Física'],
        'Vendas': [len(marketplace), len(farmacia_fisica)],
        'Tempo Médio (h)': [marketplace['tempo_horas'].mean(), farmacia_fisica['tempo_horas'].mean()],
        'Mediana (h)': [marketplace['tempo_horas'].median(), farmacia_fisica['tempo_horas'].median()],
        'Desvio Padrão': [marketplace['tempo_horas'].std(), farmacia_fisica['tempo_horas'].std()]
    })

    # Métricas de comparação
    diff_media = farmacia_fisica['tempo_horas'].mean() - marketplace['tempo_horas'].mean()
    pct_diff = (diff_media / marketplace['tempo_horas'].mean()) * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Marketplace", f"{len(marketplace):,}", f"{marketplace['tempo_horas'].mean():.1f}h médio")
    col2.metric("Farmácia Física", f"{len(farmacia_fisica):,}", f"{farmacia_fisica['tempo_horas'].mean():.1f}h médio")
    col3.metric("Diferença", f"{diff_media:+.1f}h", f"{pct_diff:+.1f}%")
    col4.metric("Hipótese", "✅ Confirmada" if diff_media > 0 else "❌ Rejeitada", "Marketplace mais rápido!")

    # Visualizações
    col1, col2 = st.columns(2)

    with col1:
        # Box plot comparativo
        fig_box = go.Figure()
        fig_box.add_trace(go.Box(
            y=marketplace['tempo_horas'], name="Marketplace",
            marker_color=COLORS["primary"], boxmean=True
        ))
        fig_box.add_trace(go.Box(
            y=farmacia_fisica['tempo_horas'], name="Farmácia Física",
            marker_color=COLORS["secondary"], boxmean=True
        ))
        fig_box.update_layout(
            height=300, yaxis_title="Tempo de Venda (horas)",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            title="Distribuição do Tempo de Venda por Canal"
        )
        st.plotly_chart(fig_box, use_container_width=True)

    with col2:
        # Barras de tempo médio
        fig_bars = go.Figure()
        fig_bars.add_trace(go.Bar(
            x=['Marketplace', 'Farmácia Física'],
            y=[marketplace['tempo_horas'].mean(), farmacia_fisica['tempo_horas'].mean()],
            marker_color=[COLORS["primary"], COLORS["secondary"]],
            text=[f"{marketplace['tempo_horas'].mean():.1f}h", f"{farmacia_fisica['tempo_horas'].mean():.1f}h"],
            textposition="auto"
        ))
        fig_bars.update_layout(
            height=300, yaxis_title="Tempo Médio (horas)",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            title="Tempo Médio de Venda por Canal"
        )
        st.plotly_chart(fig_bars, use_container_width=True)

    # Distribuição percentual por faixas de tempo
    st.markdown("#### 📈 Distribuição por Faixas de Tempo")

    tempo_bins = [0, 1, 6, 24, 72, 168, 720, float('inf')]
    tempo_labels = ['< 1h', '1-6h', '6-24h', '1-3 dias', '3-7 dias', '7-30 dias', '> 30 dias']

    marketplace_faixas = pd.cut(marketplace['tempo_horas'], bins=tempo_bins, labels=tempo_labels, right=False).value_counts(sort=False)
    farmacia_faixas = pd.cut(farmacia_fisica['tempo_horas'], bins=tempo_bins, labels=tempo_labels, right=False).value_counts(sort=False)

    faixas_df = pd.DataFrame({
        'Faixa': tempo_labels,
        'Marketplace': marketplace_faixas.values,
        'Farmácia Física': farmacia_faixas.values
    })

    # Calcular percentuais
    faixas_df['MP %'] = (faixas_df['Marketplace'] / faixas_df['Marketplace'].sum() * 100).round(1)
    faixas_df['FF %'] = (faixas_df['Farmácia Física'] / faixas_df['Farmácia Física'].sum() * 100).round(1)

    # Gráfico de barras agrupadas
    fig_faixas = go.Figure()
    fig_faixas.add_trace(go.Bar(
        name="Marketplace", x=faixas_df['Faixa'], y=faixas_df['MP %'],
        marker_color=COLORS["primary"], text=faixas_df['MP %'].map("{:.1f}%".format), textposition="outside"
    ))
    fig_faixas.add_trace(go.Bar(
        name="Farmácia Física", x=faixas_df['Faixa'], y=faixas_df['FF %'],
        marker_color=COLORS["secondary"], text=faixas_df['FF %'].map("{:.1f}%".format), textposition="outside"
    ))
    fig_faixas.update_layout(
        barmode="group", height=400, yaxis_title="Percentual de Vendas",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        title="Distribuição Percentual por Faixas de Tempo"
    )
    st.plotly_chart(fig_faixas, use_container_width=True)

    st.divider()

    # Análise da Idade do Paciente
    st.markdown("### 👶 Análise da Idade do Paciente")

    # Calcular idade do paciente
    dff_with_age = dff.copy()
    dff_with_age["nascimentopaciente"] = pd.to_datetime(dff_with_age["nascimentopaciente"])
    dff_with_age["idade_paciente"] = (pd.Timestamp.now() - dff_with_age["nascimentopaciente"]).dt.days / 365.25
    dff_with_age = dff_with_age.dropna(subset=["idade_paciente"])

    # Criar faixas etárias
    bins = [0, 18, 25, 35, 45, 55, 65, float('inf')]
    labels = ['≤18', '19-25', '26-35', '36-45', '46-55', '56-65', '65+']
    dff_with_age['faixa_etaria'] = pd.cut(dff_with_age['idade_paciente'], bins=bins, labels=labels, right=False)

    # Análise por faixa etária
    age_analysis = dff_with_age.groupby('faixa_etaria', observed=True).agg({
        'idprescricao': 'count',
        'visualizadapaciente': 'sum',
        'itemvendido': 'sum'
    }).reset_index()

    age_analysis['open_rate'] = age_analysis['visualizadapaciente'] / age_analysis['idprescricao']
    age_analysis['conv_rate'] = age_analysis['itemvendido'] / age_analysis['visualizadapaciente'].replace(0, 1)

    # Gráfico de barras para open rate e conversão por faixa etária
    fig_age_rates = go.Figure()
    fig_age_rates.add_trace(go.Bar(
        name="Open Rate", x=age_analysis["faixa_etaria"],
        y=age_analysis["open_rate"], marker_color=COLORS["primary"],
        text=age_analysis["open_rate"].map("{:.1%}".format), textposition="outside",
    ))
    fig_age_rates.add_trace(go.Bar(
        name="Conversão", x=age_analysis["faixa_etaria"],
        y=age_analysis["conv_rate"], marker_color=COLORS["success"],
        text=age_analysis["conv_rate"].map("{:.1%}".format), textposition="outside",
    ))
    fig_age_rates.update_layout(
        barmode="group", height=400, yaxis_tickformat=".0%",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        title="Open Rate e Conversão por Faixa Etária",
        xaxis_title="Faixa Etária", yaxis_title="Taxa"
    )
    st.plotly_chart(fig_age_rates, use_container_width=True)

    # Análise por gênero e faixa etária
    st.markdown("#### 📊 Por Gênero e Faixa Etária")

    gender_age = dff_with_age.groupby(['faixa_etaria', 'sexopaciente'], observed=True).agg({
        'idprescricao': 'count',
        'visualizadapaciente': 'sum',
        'itemvendido': 'sum'
    }).reset_index()

    gender_age['open_rate'] = gender_age['visualizadapaciente'] / gender_age['idprescricao']
    gender_age['conv_rate'] = gender_age['itemvendido'] / gender_age['visualizadapaciente'].replace(0, 1)

    # Pivot para facilitar visualização
    gender_pivot = gender_age.pivot(index='faixa_etaria', columns='sexopaciente',
                                   values=['open_rate', 'conv_rate'])

    col1, col2 = st.columns(2)
    with col1:
        # Open Rate por gênero
        fig_gender_open = px.bar(
            gender_age, x="faixa_etaria", y="open_rate", color="sexopaciente",
            barmode="group", color_discrete_sequence=[COLORS["primary"], COLORS["secondary"]],
            labels={"faixa_etaria": "Faixa Etária", "open_rate": "Open Rate", "sexopaciente": "Gênero"},
            title="Open Rate por Gênero e Faixa Etária"
        )
        fig_gender_open.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gender_open, use_container_width=True)

    with col2:
        # Conversão por gênero
        fig_gender_conv = px.bar(
            gender_age, x="faixa_etaria", y="conv_rate", color="sexopaciente",
            barmode="group", color_discrete_sequence=[COLORS["success"], COLORS["warning"]],
            labels={"faixa_etaria": "Faixa Etária", "conv_rate": "Conversão", "sexopaciente": "Gênero"},
            title="Conversão por Gênero e Faixa Etária"
        )
        fig_gender_conv.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gender_conv, use_container_width=True)

    # Análise por estado (top 5)
    st.markdown("#### 📍 Por Estado (Top 5)")

    top_states = dff_with_age['estadopaciente'].value_counts().head(5).index

    state_age_data = []
    for state in top_states:
        state_data = dff_with_age[dff_with_age['estadopaciente'] == state]
        state_analysis = state_data.groupby('faixa_etaria', observed=True).agg({
            'idprescricao': 'count',
            'visualizadapaciente': 'sum',
            'itemvendido': 'sum'
        }).reset_index()

        state_analysis['open_rate'] = state_analysis['visualizadapaciente'] / state_analysis['idprescricao']
        state_analysis['conv_rate'] = state_analysis['itemvendido'] / state_analysis['visualizadapaciente'].replace(0, 1)
        state_analysis['estado'] = state

        state_age_data.append(state_analysis)

    state_age_df = pd.concat(state_age_data, ignore_index=True)

    # Gráfico de conversão por estado e faixa etária
    fig_state_age = px.bar(
        state_age_df, x="faixa_etaria", y="conv_rate", color="estado",
        barmode="group", color_discrete_sequence=PALETTE,
        labels={"faixa_etaria": "Faixa Etária", "conv_rate": "Conversão", "estado": "Estado"},
        title="Conversão por Estado e Faixa Etária (Top 5 Estados)"
    )
    fig_state_age.update_layout(height=400, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_state_age, use_container_width=True)

    st.divider()

    st.markdown("### Pacientes que NÃO abriram a receita — por Estado")
    nao_abriu = (
        dff.groupby(["estadopaciente", "idprescricao"])["visualizadapaciente"]
        .max()
        .reset_index()
    )
    nao_abriu["nao_abriu"] = ~nao_abriu["visualizadapaciente"]
    nao_abriu_est = nao_abriu.groupby("estadopaciente").agg(
        total=("idprescricao", "count"),
        nao_abriu=("nao_abriu", "sum"),
    ).reset_index()
    nao_abriu_est["taxa_nao_abriu"] = nao_abriu_est["nao_abriu"] / nao_abriu_est["total"]
    nao_abriu_est = nao_abriu_est[nao_abriu_est["total"] >= 30].sort_values(
        "taxa_nao_abriu", ascending=False
    ).head(15)

    fig_na = px.bar(
        nao_abriu_est, x="taxa_nao_abriu", y="estadopaciente", orientation="h",
        color="taxa_nao_abriu", color_continuous_scale="Reds",
        text=nao_abriu_est["taxa_nao_abriu"].map("{:.1%}".format),
        labels={"taxa_nao_abriu": "Taxa Não Abertura", "estadopaciente": "Estado"},
    )
    fig_na.update_layout(height=400, yaxis={"categoryorder": "total ascending"},
                          coloraxis_showscale=False,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_na, use_container_width=True)

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Retenção de Médicos (Prescrições/Médico)")
        med_presc = (
            dff.groupby("idmedico")["idprescricao"]
            .nunique()
            .value_counts()
            .reset_index()
        )
        med_presc.columns = ["Prescrições por Médico", "Médicos"]
        med_presc = med_presc.sort_values("Prescrições por Médico")
        fig_ret = px.bar(
            med_presc.head(15), x="Prescrições por Médico", y="Médicos",
            color="Médicos", color_continuous_scale="Purples",
        )
        fig_ret.update_layout(height=300, coloraxis_showscale=False,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_ret, use_container_width=True)

    with col2:
        st.markdown("### Prescrições por Convênio")
        conv_df = dff.groupby("idconvenio")["idprescricao"].nunique().reset_index()
        conv_df.columns = ["Convênio", "Prescrições"]
        conv_df["Tipo"] = conv_df["Convênio"].apply(
            lambda x: "Particular" if pd.isna(x) else f"Convênio {int(x)}")
        fig_conv = px.bar(
            conv_df.sort_values("Prescrições", ascending=False).head(10),
            x="Tipo", y="Prescrições",
            color="Prescrições", color_continuous_scale="Blues",
        )
        fig_conv.update_layout(height=300, coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_conv, use_container_width=True)

    st.divider()
    st.markdown("### 💡 Oportunidades de Melhoria Identificadas")

    # Calcular estatísticas de convênio para os insights
    convenio_stats = dff.groupby("idconvenio")["idprescricao"].nunique().reset_index()
    convenio_stats.columns = ["Convênio", "Prescrições"]
    com_convenio = convenio_stats[convenio_stats["Convênio"].notna()]["Prescrições"].sum()
    sem_convenio = convenio_stats[convenio_stats["Convênio"].isna()]["Prescrições"].sum()
    total_presc_insights = convenio_stats["Prescrições"].sum()

    # Calcular idade e faixas etárias para insights
    dff_age = dff.copy()
    dff_age["nascimentopaciente"] = pd.to_datetime(dff_age["nascimentopaciente"])
    dff_age["idade_paciente"] = (pd.Timestamp.now() - dff_age["nascimentopaciente"]).dt.days / 365.25
    dff_age = dff_age.dropna(subset=["idade_paciente"])
    bins = [0, 18, 25, 35, 45, 55, 65, float('inf')]
    labels = ['≤18', '19-25', '26-35', '36-45', '46-55', '56-65', '65+']
    dff_age['faixa_etaria'] = pd.cut(dff_age['idade_paciente'], bins=bins, labels=labels, right=False)

    # Calcular open rate e conversão por faixa etária
    age_stats = dff_age.groupby('faixa_etaria').agg(
        total_presc=('idprescricao', 'nunique'),
        open_rate=('visualizadapaciente', 'mean'),
        conv_rate=('itemvendido', lambda x: (x > 0).mean())
    ).reset_index()

    # Encontrar a faixa com melhor engajamento (maior open rate)
    best_engagement = age_stats.loc[age_stats['open_rate'].idxmax()]
    best_engagement_faixa = best_engagement['faixa_etaria']
    best_engagement_open = best_engagement['open_rate']

    # Encontrar a faixa com melhor conversão entre os que visualizaram
    age_conv = dff_age[dff_age['visualizadapaciente']].groupby('faixa_etaria').agg(
        conv_rate=('itemvendido', lambda x: (x > 0).mean())
    ).reset_index()
    best_conv = age_conv.loc[age_conv['conv_rate'].idxmax()]
    best_conv_faixa = best_conv['faixa_etaria']
    best_conv_rate = best_conv['conv_rate']

    insights = [
        ("🔔 Notificação Push para Receitas Não Abertas",
         f"**{(1 - dff.groupby('idprescricao')['visualizadapaciente'].max().mean()):.1%}** das prescrições não são visualizadas. "
         "Implementar notificações (SMS/WhatsApp) poderia aumentar significativamente o open rate."),
        ("⏱️ Marketplace é 29.5h mais Rápido!",
         f"O marketplace tem tempo médio de venda de **{marketplace['tempo_horas'].mean():.1f}h** vs **{farmacia_fisica['tempo_horas'].mean():.1f}h** da farmácia física. "
         "Investir em UX digital e expandir marketplace pode acelerar vendas e melhorar experiência do paciente."),
        (f"👶 {best_engagement_faixa}: Melhor Engajamento",
         f"Pacientes de {best_engagement_faixa} têm **{best_engagement_open:.1%}** de open rate (maior) e **{best_engagement['conv_rate']:.1%}** de conversão. "
         "Campanhas direcionadas para essa faixa etária podem maximizar ROI em marketing digital."),
        (f"👴 {best_conv_faixa}: Melhor Conversão ({best_conv_rate:.1%})",
         f"Pacientes de {best_conv_faixa} convertem **{best_conv_rate:.1%}** quando abrem a receita, apesar de menor engajamento. "
         "Foco em canais tradicionais (farmacia física) e suporte personalizado para essa faixa etária."),
        (f"🏦 Convênios: {com_convenio/total_presc_insights:.1%} das Prescrições",
         f"**{com_convenio:,}** prescrições têm convênio vs **{sem_convenio:,}** particulares. "
         "Parcerias estratégicas com planos de saúde podem aumentar volume e fidelização."),
        ("📍 Expansão Regional Direcionada",
         "SP concentra ~49% das prescrições. Estados como MG, RS e PR têm volume relevante "
         "mas taxas de conversão menores — oportunidade de parceria com farmácias locais."),
        ("🏥 Engajamento de Médicos com Baixo Volume",
         "Parte significativa dos médicos emite apenas 1–2 prescrições. "
         "Programa de onboarding e suporte dedicado pode aumentar retenção e frequência de uso."),
        ("💊 Crescimento do Canal Digital",
         f"Marketplace representa **{len(marketplace)/(len(marketplace)+len(farmacia_fisica)):.1%}** das vendas mas vende **29.5h mais rápido**. "
         "Acelerar adoção digital pode aumentar eficiência operacional e satisfação do cliente."),
    ]
    for title, desc in insights:
        with st.expander(title):
            st.markdown(desc)


# ─────────────────────────────────────────────
# PAGE: DESCRIÇÃO DE METRICAS
# ─────────────────────────────────────────────
elif page == "📈 Descrição de Métricas":
    section("📈 Descrição de Métricas", "Entenda cada indicador usado no dashboard")

    st.markdown(
        """
- **Prescrições**: número de prescrições únicas emitidas no período selecionado.
- **Pacientes Únicos**: total de pacientes diferentes que receberam prescrições.
- **Médicos Ativos**: quantidade de médicos que emitiram prescrições no período.
- **Média Diária**: média de prescrições emitidas por dia, considerando apenas o período filtrado.
- **Open Rate**: taxa de abertura das prescrições, calculada como o percentual de prescrições em que o paciente visualizou a receita.
- **Taxa de Conversão**: percentual de prescrições visualizadas que resultaram em venda.

### Diferença entre Conversão Marketplace e Físico

- **Marketplace**: o paciente compra o medicamento por canais digitais, como a loja online ou o aplicativo da plataforma. Geralmente a conversão do marketplace é medida sobre as prescrições visualizadas que acabam em compra pelo canal digital.
- **Físico**: o paciente efetua a compra em uma farmácia física. A conversão física também é medida em relação às prescrições visualizadas que terminam em venda na loja presencial.

A comparação entre marketplace e físico ajuda a identificar se o cliente está preferindo comprar digitalmente ou em ponto de venda, e se há oportunidades de melhorar comunicação, frete, estoque ou oferta de preço para cada canal.

### Por que isso importa?

- Uma **alta open rate** mostra que a comunicação da receita digital está chegando ao paciente.
- Uma **boa taxa de conversão** indica que, após abrir a receita, o paciente encontra o medicamento e conclui a compra.
- Diferenças entre **marketplace e físico** podem revelar problemas de experiência de compra, disponibilidade do produto ou preferência do público.

"""
    )


# ─────────────────────────────────────────────
# PAGE: BUILD IT UP
# ─────────────────────────────────────────────
elif page == "🔧 Build It Up":
    section("🔧 Build It Up", "Explore os dados de forma personalizada")

    # Available columns for dimensions and filters
    available_columns = {
        'Data': ['data', 'dataprescricao', 'datavenda', 'semana', 'mes', 'dia_semana'],
        'Localização': ['estadopaciente', 'cidadepaciente', 'estado'],
        'Pessoas': ['idpaciente', 'idmedico', 'genero', 'idade', 'sexopaciente'],
        'Medicamentos': ['idmedicamento', 'nome', 'antimicrobiano', 'controleespecial', 'mip'],
        'Transação': ['idprescricao', 'idconvenio', 'canalvenda', 'visualizadapaciente', 'itemvendido'],
        'Outros': ['hora']
    }

    # Flatten available columns
    all_columns = [col for cols in available_columns.values() for col in cols]

    # Metrics definitions
    metrics = {
        'Contagem de Prescrições': ('idprescricao', 'nunique'),
        'Contagem de Pacientes': ('idpaciente', 'nunique'),
        'Contagem de Médicos': ('idmedico', 'nunique'),
        'Contagem de Medicamentos': ('idmedicamento', 'nunique'),
        'Soma de Itens Vendidos': ('itemvendido', 'sum'),
        'Taxa de Visualização': ('visualizadapaciente', 'mean'),
        'Taxa de Conversão': ('itemvendido', lambda x: (x > 0).mean()),
        'Valor Médio': ('itemvendido', 'mean'),
    }

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### ⚙️ Configurações")

        # Dimensions selection
        st.markdown("**📏 Dimensões (agrupar por)**")
        selected_dimensions = st.multiselect(
            "Selecione as dimensões:",
            all_columns,
            default=['data'],
            help="Escolha as colunas para agrupar os dados"
        )

        # Filters
        st.markdown("**🔍 Filtros**")
        filters = {}

        # Specific filters as text inputs (comma-separated values)
        st.markdown("**IDs e Identificadores**")
        col_id1, col_id2 = st.columns(2)
        with col_id1:
            id_pedido_input = st.text_input(
                "ID Pedido:",
                placeholder="Digite IDs separados por vírgula (ex: 123,456,789)",
                help="Filtrar por IDs específicos de pedido separados por vírgula"
            )
            if id_pedido_input.strip():
                try:
                    filters['idpedido'] = [int(x.strip()) for x in id_pedido_input.split(',') if x.strip()]
                except ValueError:
                    st.error("IDs de pedido devem ser números separados por vírgula")

            id_medico_input = st.text_input(
                "ID Médico:",
                placeholder="Digite IDs separados por vírgula (ex: 101,202,303)",
                help="Filtrar por IDs específicos de médico separados por vírgula"
            )
            if id_medico_input.strip():
                try:
                    filters['idmedico'] = [int(x.strip()) for x in id_medico_input.split(',') if x.strip()]
                except ValueError:
                    st.error("IDs de médico devem ser números separados por vírgula")

        with col_id2:
            id_medicamento_input = st.text_input(
                "ID Medicamento:",
                placeholder="Digite IDs separados por vírgula (ex: 1001,1002,1003)",
                help="Filtrar por IDs específicos de medicamento separados por vírgula"
            )
            if id_medicamento_input.strip():
                try:
                    filters['idmedicamento'] = [int(x.strip()) for x in id_medicamento_input.split(',') if x.strip()]
                except ValueError:
                    st.error("IDs de medicamento devem ser números separados por vírgula")

            id_convenio_input = st.text_input(
                "ID Convênio:",
                placeholder="Digite IDs separados por vírgula (ex: 1,2,3)",
                help="Filtrar por IDs específicos de convênio separados por vírgula"
            )
            if id_convenio_input.strip():
                try:
                    filters['idconvenio'] = [float(x.strip()) for x in id_convenio_input.split(',') if x.strip()]
                except ValueError:
                    st.error("IDs de convênio devem ser números separados por vírgula")

        st.markdown("**Localização**")
        col_loc1, col_loc2 = st.columns(2)
        with col_loc1:
            estado_input = st.text_input(
                "Estado:",
                placeholder="Digite estados separados por vírgula (ex: SP,RJ,MG)",
                help="Filtrar por estados separados por vírgula"
            )
            if estado_input.strip():
                filters['estado'] = [x.strip() for x in estado_input.split(',') if x.strip()]

        with col_loc2:
            cidade_input = st.text_input(
                "Cidade:",
                placeholder="Digite cidades separadas por vírgula (ex: São Paulo,Rio de Janeiro,Belo Horizonte)",
                help="Filtrar por cidades separadas por vírgula"
            )
            if cidade_input.strip():
                filters['cidadepaciente'] = [x.strip() for x in cidade_input.split(',') if x.strip()]

        st.markdown("**Demografia e Medicamentos**")
        col_demo1, col_demo2 = st.columns(2)
        with col_demo1:
            idade_input = st.text_input(
                "Idade:",
                placeholder="Digite idades separadas por vírgula (ex: 25,30,35)",
                help="Filtrar por idades específicas separadas por vírgula"
            )
            if idade_input.strip():
                try:
                    filters['idade'] = [int(x.strip()) for x in idade_input.split(',') if x.strip()]
                except ValueError:
                    st.error("Idades devem ser números separados por vírgula")

        with col_demo2:
            id_prescricao_input = st.text_input(
                "ID Prescrição:",
                placeholder="Digite IDs separados por vírgula (ex: 5001,5002,5003)",
                help="Filtrar por IDs específicos de prescrição separados por vírgula"
            )
            if id_prescricao_input.strip():
                try:
                    filters['idprescricao'] = [int(x.strip()) for x in id_prescricao_input.split(',') if x.strip()]
                except ValueError:
                    st.error("IDs de prescrição devem ser números separados por vírgula")

        st.markdown("**Classe do Medicamento**")
        classe_input = st.text_input(
            "Classe Medicamento:",
            placeholder="Digite classes separadas por vírgula (ex: Antibiótico,Controle Especial,MIP)",
            help="Filtrar por classes de medicamento separadas por vírgula"
        )
        if classe_input.strip():
            classes = [x.strip().lower() for x in classe_input.split(',') if x.strip()]
            if 'antibiótico' in classes or 'antimicrobiano' in classes:
                filters['antimicrobiano'] = True
            if 'controle especial' in classes:
                filters['controleespecial'] = True
            if 'mip' in classes:
                filters['mip'] = True

        # Metrics selection
        st.markdown("**📊 Métricas**")
        selected_metrics = st.multiselect(
            "Selecione as métricas:",
            list(metrics.keys()),
            default=['Contagem de Prescrições'],
            help="Escolha as métricas para calcular"
        )

        # Visualization type
        st.markdown("**📈 Visualização**")
        viz_type = st.selectbox(
            "Tipo de visualização:",
            ["Tabela", "Gráfico de Barras", "Gráfico de Linha", "Gráfico de Pizza"],
            help="Escolha como visualizar os dados"
        )

        # Apply button
        apply_filters = st.button("🚀 Aplicar e Visualizar", type="primary")

    with col2:
        st.markdown("### 📊 Resultados")

        if apply_filters and selected_dimensions and selected_metrics:
            # Apply filters
            filtered_df = dff.copy()

            for col, filter_val in filters.items():
                if col in ['antimicrobiano', 'controleespecial', 'mip']:
                    # Boolean filters for medication classes
                    if filter_val:
                        filtered_df = filtered_df[filtered_df[col] == True]
                elif isinstance(filter_val, list) and filter_val:  # List filter (comma-separated values)
                    filtered_df = filtered_df[filtered_df[col].isin(filter_val)]
                elif isinstance(filter_val, tuple) and len(filter_val) == 2:  # Slider filter
                    filtered_df = filtered_df[
                        (filtered_df[col] >= filter_val[0]) &
                        (filtered_df[col] <= filter_val[1])
                    ]

            # Group by dimensions and calculate metrics
            if selected_dimensions:
                grouped = filtered_df.groupby(selected_dimensions)

                results = {}
                for metric_name in selected_metrics:
                    col, agg_func = metrics[metric_name]
                    if agg_func == 'nunique':
                        results[metric_name] = grouped[col].nunique()
                    elif agg_func == 'sum':
                        results[metric_name] = grouped[col].sum()
                    elif agg_func == 'mean':
                        results[metric_name] = grouped[col].mean()
                    elif callable(agg_func):
                        results[metric_name] = grouped[col].agg(agg_func)

                # Combine results
                result_df = pd.DataFrame(results).reset_index()

                # Generate and display applied query
                st.markdown("### 🔍 Query Aplicada")
                query_parts = []

                # Base query with JOINs (reflecting the actual data structure)
                base_query = """
FROM prescricaomedicamento p
LEFT JOIN medicamentos m ON p.idmedicamento = m.idmedicamento
LEFT JOIN medicos md ON p.idmedico = md.idmedico
WHERE p.dataprescricao BETWEEN '{date_range[0]}' AND '{date_range[1]}'"""

                # Add additional filters
                filter_conditions = []
                for col, filter_val in filters.items():
                    if col in ['antimicrobiano', 'controleespecial', 'mip'] and filter_val:
                        if col in ['antimicrobiano', 'controleespecial', 'mip']:
                            filter_conditions.append(f"m.{col} = True")
                    elif isinstance(filter_val, list) and filter_val:
                        if len(filter_val) <= 5:
                            filter_conditions.append(f"p.{col} IN ({', '.join(map(repr, filter_val))})")
                        else:
                            filter_conditions.append(f"p.{col} IN ({len(filter_val)} valores)")
                    elif isinstance(filter_val, tuple) and len(filter_val) == 2:
                        filter_conditions.append(f"p.{col} BETWEEN {filter_val[0]} AND {filter_val[1]}")

                # Build SELECT clause with metrics
                if selected_metrics:
                    select_parts = []
                    for metric_name in selected_metrics:
                        col, agg_func = metrics[metric_name]
                        if agg_func == 'nunique':
                            select_parts.append(f"COUNT(DISTINCT p.{col}) as \"{metric_name}\"")
                        elif agg_func == 'sum':
                            select_parts.append(f"SUM(p.{col}) as \"{metric_name}\"")
                        elif agg_func == 'mean':
                            select_parts.append(f"AVG(p.{col}) as \"{metric_name}\"")
                        elif callable(agg_func):
                            if metric_name == 'Taxa de Visualização':
                                select_parts.append(f"AVG(p.visualizadapaciente) as \"{metric_name}\"")
                            elif metric_name == 'Taxa de Conversão':
                                select_parts.append(f"AVG(CASE WHEN p.visualizadapaciente = 1 THEN CASE WHEN p.itemvendido > 0 THEN 1 ELSE 0 END ELSE NULL END) as \"{metric_name}\"")
                            else:
                                select_parts.append(f"COUNT(*) as \"{metric_name}\"")
                    select_clause = f"SELECT {', '.join(select_parts)}"
                else:
                    select_clause = "SELECT *"

                # Add dimensions to GROUP BY
                if selected_dimensions:
                    group_cols = []
                    for dim in selected_dimensions:
                        if dim in ['nome', 'antimicrobiano', 'controleespecial', 'mip']:
                            group_cols.append(f"m.{dim}")
                        elif dim in ['especialidade', 'estado', 'genero', 'idade']:
                            group_cols.append(f"md.{dim}")
                        else:
                            group_cols.append(f"p.{dim}")
                    group_clause = f"GROUP BY {', '.join(group_cols)}"
                else:
                    group_clause = ""

                # Construct full query
                full_query = f"{select_clause}\n{base_query.format(date_range=date_range)}"
                if filter_conditions:
                    full_query += f"\nAND {' AND '.join(filter_conditions)}"
                if group_clause:
                    full_query += f"\n{group_clause}"

                # Display the query
                st.code(full_query, language="sql")

                st.markdown("---")

                # Display results
                if viz_type == "Tabela":
                    st.dataframe(result_df, use_container_width=True)

                elif viz_type in ["Gráfico de Barras", "Gráfico de Linha"]:
                    if len(selected_dimensions) == 1 and len(selected_metrics) == 1:
                        x_col = selected_dimensions[0]
                        y_col = selected_metrics[0]

                        if viz_type == "Gráfico de Barras":
                            fig = px.bar(result_df, x=x_col, y=y_col,
                                       title=f"{y_col} por {x_col}",
                                       color_discrete_sequence=[COLORS["primary"]])
                        else:  # Line chart
                            fig = px.line(result_df, x=x_col, y=y_col,
                                        title=f"{y_col} por {x_col}",
                                        markers=True, color_discrete_sequence=[COLORS["primary"]])

                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)"
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    elif len(selected_dimensions) == 1 and len(selected_metrics) > 1:
                        # Multiple metrics as lines/bars
                        melted_df = result_df.melt(
                            id_vars=selected_dimensions,
                            value_vars=selected_metrics,
                            var_name='Métrica',
                            value_name='Valor'
                        )

                        if viz_type == "Gráfico de Barras":
                            fig = px.bar(melted_df, x=selected_dimensions[0], y='Valor',
                                       color='Métrica', barmode='group',
                                       title=f"Métricas por {selected_dimensions[0]}")
                        else:
                            fig = px.line(melted_df, x=selected_dimensions[0], y='Valor',
                                        color='Métrica', markers=True,
                                        title=f"Métricas por {selected_dimensions[0]}")

                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Para gráficos, selecione exatamente 1 dimensão e 1 ou mais métricas.")

                elif viz_type == "Gráfico de Pizza":
                    if len(selected_metrics) == 1 and len(result_df) <= 20:
                        metric_name = selected_metrics[0]
                        fig = px.pie(result_df, names=selected_dimensions[0] if len(selected_dimensions) == 1 else result_df.index,
                                   values=metric_name, title=f"{metric_name} por categoria",
                                   color_discrete_sequence=PALETTE)
                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Para gráfico de pizza, selecione exatamente 1 métrica e no máximo 20 categorias.")

                # Download CSV
                csv = result_df.to_csv(index=False)
                st.download_button(
                    label="📥 Baixar CSV",
                    data=csv,
                    file_name="dados_personalizados.csv",
                    mime="text/csv",
                    key="download_csv"
                )

                st.markdown(f"**Total de registros:** {len(result_df)}")

            else:
                st.warning("Selecione pelo menos uma dimensão para agrupar os dados.")

        elif apply_filters:
            st.warning("Selecione pelo menos uma dimensão e uma métrica.")

        else:
            st.info("Configure suas dimensões, filtros e métricas, depois clique em 'Aplicar e Visualizar' para ver os resultados.")


# ─────────────────────────────────────────────
# PAGE: AGENTE IA
# ─────────────────────────────────────────────
elif page == "🤖 Agente IA":
    section("🤖 Agente de IA", "Converse com os dados usando Claude")

    # Build data context summary
    @st.cache_data
    def build_context(df_hash):
        total_presc = dff["idprescricao"].nunique()
        total_pacs = dff["idpaciente"].nunique()
        total_med = dff["idmedico"].nunique()
        media_diaria = dff.groupby("data")["idprescricao"].nunique().mean()

        presc_lv = (
            dff.groupby("idprescricao")
            .agg(visualizada=("visualizadapaciente", "max"),
                 vendido=("itemvendido", lambda x: (x > 0).any()))
            .reset_index()
        )
        open_rate = presc_lv["visualizada"].mean()
        conv_rate = presc_lv[presc_lv["visualizada"]]["vendido"].mean()

        top_esp = (dff.groupby("especialidade")["idprescricao"].nunique()
                   .sort_values(ascending=False).head(5).to_dict())
        top_med_name = (dff.groupby("nome")["idprescricao"].nunique()
                        .sort_values(ascending=False).head(5).to_dict())
        canal_dist = dff["canalvenda"].value_counts().to_dict()
        state_dist = dff["estadopaciente"].value_counts().head(5).to_dict()
        dow_open = (
            dff.groupby(["dia_semana", "idprescricao"])["visualizadapaciente"]
            .max().reset_index()
            .groupby("dia_semana")["visualizadapaciente"].mean()
            .sort_values(ascending=False).head(3).to_dict()
        )

        vendas_df = dff[dff["datavenda"].notna()].copy()
        vendas_df["tempo_h"] = (vendas_df["datavenda"] - vendas_df["dataprescricao"]).dt.total_seconds() / 3600
        vendas_df = vendas_df[vendas_df["tempo_h"] >= 0]

        return f"""
Você é um analista de dados sênior da empresa Saude+, plataforma digital para emissão de prescrições médicas eletrônicas.

RESUMO DOS DADOS (período: {dff['dataprescricao'].min().date()} a {dff['dataprescricao'].max().date()}):

- Total de prescrições únicas: {total_presc:,}
- Total de pacientes únicos: {total_pacs:,}
- Total de médicos ativos: {total_med:,}
- Média de prescrições diárias: {media_diaria:.0f}
- Open Rate geral: {open_rate:.1%} (prescrições visualizadas / total)
- Taxa de Conversão: {conv_rate:.1%} (vendas / prescrições visualizadas)

TOP 5 ESPECIALIDADES (por prescrições):
{json.dumps(top_esp, ensure_ascii=False, indent=2)}

TOP 5 MEDICAMENTOS:
{json.dumps(top_med_name, ensure_ascii=False, indent=2)}

DISTRIBUIÇÃO POR CANAL DE VENDA:
{json.dumps(canal_dist, ensure_ascii=False, indent=2)}

TOP 5 ESTADOS DOS PACIENTES:
{json.dumps(state_dist, ensure_ascii=False, indent=2)}

DIAS COM MAIOR OPEN RATE:
{json.dumps(dow_open, ensure_ascii=False, indent=2)}

TEMPO MEDIANO PARA COMPRA: {vendas_df['tempo_h'].median():.0f} horas
COMPRAS DENTRO DE 24H: {(vendas_df['tempo_h'] <= 24).mean():.1%} das vendas

Responda sempre em português, de forma clara e objetiva, com insights acionáveis quando possível.
Quando não souber algo específico que não está no resumo, diga isso claramente.
"""

    context = build_context(hash(str(dff.shape)))

    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key:
        st.warning("⚠️ Configure sua `ANTHROPIC_API_KEY` no arquivo `.env` para usar o agente.")
        with st.expander("Como configurar"):
            st.code("""
# Crie um arquivo .env na raiz do projeto:
ANTHROPIC_API_KEY=sk-ant-api03-...
            """)
    else:
        st.info(
            "💬 Faça perguntas sobre os dados — o agente usa Claude para interpretar e responder com base nos indicadores reais.",
            icon="🤖",
        )

        # Suggested questions
        st.markdown("**Sugestões de perguntas:**")
        sugs = [
            "Qual é o principal problema operacional identificado nos dados?",
            "Como aumentar a taxa de conversão do marketplace?",
            "Quais especialidades têm maior potencial de melhoria?",
            "Qual é o melhor dia para enviar receitas digitais?",
            "Como reduzir o número de prescrições não visualizadas?",
        ]
        cols = st.columns(len(sugs))
        for i, sug in enumerate(sugs):
            if cols[i].button(sug, key=f"sug_{i}", use_container_width=True):
                st.session_state.setdefault("messages", [])
                st.session_state["messages"].append({"role": "user", "content": sug})

        # Chat history
        if "messages" not in st.session_state:
            st.session_state["messages"] = []

        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Pergunte sobre os dados…"):
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analisando…"):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        response = client.messages.create(
                            model="claude-opus-4-5",
                            max_tokens=1024,
                            system=context,
                            messages=[
                                {"role": m["role"], "content": m["content"]}
                                for m in st.session_state["messages"]
                            ],
                        )
                        answer = response.content[0].text
                    except Exception as e:
                        answer = f"❌ Erro ao chamar a API: {e}"

                st.markdown(answer)

            st.session_state["messages"].append({"role": "assistant", "content": answer})

        if st.session_state.get("messages"):
            if st.button("🗑️ Limpar conversa"):
                st.session_state["messages"] = []
                st.rerun()
