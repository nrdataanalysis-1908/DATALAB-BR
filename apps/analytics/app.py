from __future__ import annotations

import io
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from catalog_data import load_catalog

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "catalog" / "tse" / "datasets" / "manifest.json"
MANIFEST_PATH = Path(os.getenv("TSE_CATALOG_MANIFEST", str(DEFAULT_MANIFEST)))
PALETTE = ["#60E6FF", "#38BDF8", "#A3E635", "#818CF8", "#F59E0B", "#F472B6", "#2DD4BF"]

st.set_page_config(
    page_title="Brasil Eleitoral DataLab",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');
    :root { --nr-cyan:#60E6FF; --nr-blue:#38BDF8; --nr-green:#A3E635; }
    .stApp { background: radial-gradient(ellipse at 50% -15%, #15334a 0, #0a1420 42%, #07111b 78%); }
    [data-testid="stSidebar"] { background: linear-gradient(180deg,#0b1926,#07111b); border-right:1px solid #1d3b50; }
    h1,h2,h3 { font-family:Inter,sans-serif; letter-spacing:-.035em; }
    h1 { color:var(--nr-cyan); font-weight:800; }
    h2,h3 { color:#e7f5ff; }
    [data-testid="stMetric"] { background:linear-gradient(145deg,#102538,#0a1723); border:1px solid #24465d; padding:16px 18px; border-radius:13px; }
    [data-testid="stMetricLabel"] { color:#9db5c5; font-family:'Space Mono',monospace; font-size:.68rem; letter-spacing:.08em; }
    [data-testid="stMetricValue"] { color:var(--nr-cyan); font-weight:800; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-color:#24465d; border-radius:14px; }
    .nr-eyebrow { color:#91aabb; font-family:'Space Mono',monospace; font-size:.68rem; letter-spacing:.18em; }
    .nr-subtitle { color:#a9bdcb; font-size:1rem; line-height:1.65; max-width:850px; }
    .nr-status { display:inline-block; border:1px solid #315b45; border-radius:5px; color:#b8ff5c; padding:5px 9px; font: .68rem 'Space Mono',monospace; letter-spacing:.08em; }
    .nr-panel-title { color:#dff6ff; font-weight:700; margin-bottom:.2rem; }
    .stDownloadButton button { border:1px solid #2a8096; color:#60e6ff; background:#10283a; }
    .stDownloadButton button:hover { border-color:#60e6ff; color:#07111b; background:#60e6ff; }
    a { color:#60e6ff !important; }
    footer { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def get_catalog(path_text: str, modified_ns: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    del modified_ns  # cache invalidation key
    return load_catalog(Path(path_text))


def dataset_frame(datasets: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in datasets:
        resources = item.get("resources") if isinstance(item.get("resources"), list) else []
        formats = Counter(
            str(resource.get("format") or "Não informado").upper()
            for resource in resources if isinstance(resource, dict)
        )
        rows.append({
            "Conjunto": item.get("title") or item.get("name") or "Sem título",
            "Identificador": item.get("name") or "",
            "Órgão": item.get("organization") or "Não informado",
            "Recursos": len(resources),
            "Formatos": ", ".join(f"{key} ({value})" for key, value in formats.most_common(4)),
            "Atualizado em": item.get("metadata_modified") or "",
            "Criado em": item.get("metadata_created") or "",
            "URL": item.get("url") or "",
            "Descrição": item.get("notes") or "",
        })
    return pd.DataFrame(rows)


def resource_frame(datasets: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in datasets:
        resources = item.get("resources") if isinstance(item.get("resources"), list) else []
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            rows.append({
                "Conjunto": item.get("title") or item.get("name") or "Sem título",
                "Órgão": item.get("organization") or "Não informado",
                "Recurso": resource.get("name") or "Sem nome",
                "Formato": str(resource.get("format") or "Não informado").upper(),
                "Tamanho (bytes)": resource.get("size"),
                "Modificado em": resource.get("last_modified") or resource.get("created") or "",
                "URL": resource.get("url") or "",
                "MIME type": resource.get("mimetype") or "",
                "Hash": resource.get("hash") or "",
            })
    return pd.DataFrame(rows)


def excel_bytes(datasets: pd.DataFrame, resources: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        datasets.to_excel(writer, index=False, sheet_name="Conjuntos")
        resources.to_excel(writer, index=False, sheet_name="Recursos")
    return output.getvalue()


def apply_filters(
    datasets: list[dict[str, Any]],
    organizations: list[str],
    formats: list[str],
    query: str,
) -> list[dict[str, Any]]:
    query_normalized = query.casefold().strip()
    selected = []
    for item in datasets:
        organization = str(item.get("organization") or "Não informado")
        if organizations and organization not in organizations:
            continue
        resources = item.get("resources") if isinstance(item.get("resources"), list) else []
        item_formats = {
            str(resource.get("format") or "Não informado").upper()
            for resource in resources if isinstance(resource, dict)
        }
        if formats and not item_formats.intersection(formats):
            continue
        searchable = " ".join(str(item.get(key) or "") for key in ("title", "name", "notes", "organization", "tags")).casefold()
        if query_normalized and query_normalized not in searchable:
            continue
        selected.append(item)
    return selected


def main() -> None:
    manifest_mtime = MANIFEST_PATH.stat().st_mtime_ns if MANIFEST_PATH.is_file() else 0
    manifest, all_datasets = get_catalog(str(MANIFEST_PATH), manifest_mtime)
    all_dataset_df = dataset_frame(all_datasets)
    all_resource_df = resource_frame(all_datasets)

    with st.sidebar:
        st.markdown("## 🗳️ BRASIL ELEITORAL")
        st.caption("NR TECH LAB · DATA INTELLIGENCE")
        st.divider()
        page = st.radio(
            "NAVEGAÇÃO",
            ["Visão geral", "Conjuntos de dados", "Explorador de recursos", "Metodologia"],
            label_visibility="visible",
        )
        st.divider()
        st.markdown("#### FILTROS DO CATÁLOGO")
        organization_options = sorted({
            str(item.get("organization") or "Não informado") for item in all_datasets
        })
        format_options = sorted({
            str(resource.get("format") or "Não informado").upper()
            for item in all_datasets
            for resource in (item.get("resources") if isinstance(item.get("resources"), list) else [])
            if isinstance(resource, dict)
        })
        selected_organizations = st.multiselect("Órgão responsável", organization_options)
        selected_formats = st.multiselect("Formato do recurso", format_options)
        search_query = st.text_input("Pesquisar catálogo", placeholder="Nome, tema ou descrição...")
        st.divider()
        st.caption(f"Manifesto: {MANIFEST_PATH.as_posix()}")
        if st.button("↻ Recarregar catálogo", use_container_width=True):
            get_catalog.clear()
            st.rerun()

    filtered = apply_filters(all_datasets, selected_organizations, selected_formats, search_query)
    filtered_datasets = dataset_frame(filtered)
    filtered_resources = resource_frame(filtered)
    resource_count = len(filtered_resources)
    org_count = filtered_datasets["Órgão"].nunique() if not filtered_datasets.empty else 0
    source_url = manifest.get("source_url") or "https://dadosabertos.tse.jus.br/"
    discovered_at = manifest.get("discovered_at") or "Não informado"

    st.markdown('<div class="nr-eyebrow">NR TECH LAB / PUBLIC DATA / TSE</div>', unsafe_allow_html=True)
    st.title("Brasil Eleitoral DataLab")
    st.markdown(
        '<div class="nr-subtitle">Plataforma de descoberta e exploração de dados públicos eleitorais. '
        'Metadados com proveniência, filtros e exportações para análise reprodutível.</div>',
        unsafe_allow_html=True,
    )
    status_label = "CATÁLOGO CARREGADO" if all_datasets else "AGUARDANDO DESCOBERTA"
    st.markdown(f'<span class="nr-status">{status_label}</span>', unsafe_allow_html=True)
    st.caption(f"Fonte: [Portal de Dados Abertos do TSE]({source_url}) · Última descoberta: {discovered_at}")

    if not all_datasets:
        st.warning("Nenhum catálogo local foi encontrado ou nenhum conjunto pôde ser carregado.")
        st.code(
            "python scripts/discover_tse_catalog.py\n"
            "streamlit run apps/analytics/app.py",
            language="powershell",
        )
        st.info("A descoberta consulta o CKAN do TSE e grava o manifesto em catalog/tse/datasets/.")
        st.stop()

    if page == "Visão geral":
        st.subheader("Panorama do catálogo")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CONJUNTOS", f"{len(filtered):,}".replace(",", "."))
        col2.metric("RECURSOS", f"{resource_count:,}".replace(",", "."))
        col3.metric("ÓRGÃOS", f"{org_count:,}".replace(",", "."))
        col4.metric("COBERTURA DO CATÁLOGO", "Completa" if manifest.get("complete") else "Parcial")
        if not filtered:
            st.info("Nenhum conjunto corresponde aos filtros selecionados.")
        else:
            left, right = st.columns(2)
            with left:
                st.markdown("#### Recursos por formato")
                if not filtered_resources.empty:
                    counts = filtered_resources["Formato"].value_counts().rename_axis("Formato").reset_index(name="Recursos")
                    fig = px.bar(counts.head(12), x="Formato", y="Recursos", color="Formato",
                                 color_discrete_sequence=PALETTE, template="plotly_dark")
                    fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10,r=10,t=20,b=10))
                    st.plotly_chart(fig, use_container_width=True)
            with right:
                st.markdown("#### Conjuntos por órgão")
                counts = filtered_datasets["Órgão"].value_counts().rename_axis("Órgão").reset_index(name="Conjuntos")
                fig = px.pie(counts, names="Órgão", values="Conjuntos", hole=.62,
                             color_discrete_sequence=PALETTE, template="plotly_dark")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10,r=10,t=20,b=10), legend_title_text="")
                st.plotly_chart(fig, use_container_width=True)
            st.markdown("#### Conjuntos com maior número de recursos")
            top = filtered_datasets.nlargest(10, "Recursos")[["Conjunto", "Órgão", "Recursos"]]
            fig = px.bar(top.sort_values("Recursos"), x="Recursos", y="Conjunto", color="Órgão",
                         orientation="h", color_discrete_sequence=PALETTE, template="plotly_dark")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10,r=10,t=15,b=10), yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        st.caption("Indicadores desta página descrevem o catálogo CKAN; não representam votos ou resultados eleitorais.")

    elif page == "Conjuntos de dados":
        st.subheader("Inventário de conjuntos")
        st.write(f"{len(filtered_datasets):,} conjunto(s) após aplicação dos filtros.".replace(",", "."))
        st.dataframe(
            filtered_datasets[["Conjunto", "Identificador", "Órgão", "Recursos", "Formatos", "Atualizado em"]],
            use_container_width=True, hide_index=True,
            column_config={"Conjunto": st.column_config.TextColumn(width="large")},
        )
        if not filtered_datasets.empty:
            options = {
                f"{item.get('title') or item.get('name')} · {item.get('name')}": item
                for item in filtered
            }
            label = st.selectbox("Detalhar conjunto", list(options))
            item = options[label]
            st.markdown("#### Detalhes do conjunto")
            st.write(item.get("notes") or "Descrição não informada pelo publicador.")
            st.json({
                "identificador": item.get("name"),
                "órgão": item.get("organization"),
                "criado_em": item.get("metadata_created"),
                "atualizado_em": item.get("metadata_modified"),
                "licença": item.get("license_title") or item.get("license_id"),
                "tags": item.get("tags") or [],
                "grupos": item.get("groups") or [],
                "fonte": item.get("source_url"),
            })
            st.markdown("#### Recursos vinculados")
            item_resources = resource_frame([item])
            st.dataframe(item_resources, use_container_width=True, hide_index=True,
                         column_config={"URL": st.column_config.LinkColumn("URL", display_text="Abrir recurso")})

    elif page == "Explorador de recursos":
        st.subheader("Explorador de recursos")
        if filtered_resources.empty:
            st.info("Não há recursos para os filtros selecionados.")
        else:
            format_filter = st.multiselect("Refinar por formato", sorted(filtered_resources["Formato"].unique()))
            resource_search = st.text_input("Pesquisar recurso ou conjunto")
            view = filtered_resources.copy()
            if format_filter:
                view = view[view["Formato"].isin(format_filter)]
            if resource_search:
                mask = view.astype(str).apply(lambda col: col.str.contains(resource_search, case=False, na=False)).any(axis=1)
                view = view[mask]
            st.caption(f"{len(view):,} recurso(s) encontrado(s).".replace(",", "."))
            st.dataframe(view, use_container_width=True, hide_index=True,
                         column_config={"URL": st.column_config.LinkColumn("URL", display_text="Abrir recurso")})
            st.download_button("Baixar recursos filtrados · CSV", view.to_csv(index=False).encode("utf-8-sig"),
                               "recursos_tse.csv", "text/csv")

    else:
        st.subheader("Metodologia, proveniência e limites")
        st.markdown(
            """
            **O que este painel apresenta**
            - Metadados dos conjuntos e recursos publicados no catálogo CKAN do TSE.
            - Organização responsável, formatos, datas, identificadores e URLs de origem.
            - Filtros e exportações aplicados aos metadados carregados localmente.

            **O que ainda não representa**
            - Não calcula votos, percentuais, comparecimento ou abstenção.
            - Não afirma cobertura integral dos arquivos eleitorais.
            - Não apresenta mapas temáticos sem dados geográficos validados.

            **Próxima etapa técnica**
            - Baixar recursos oficiais com checksum e manifesto de ingestão.
            - Validar layouts nativos e contratos de dados.
            - Normalizar tabelas Bronze, Silver e Gold antes de publicar análises eleitorais.
            """
        )
        st.json({
            "arquivo_manifesto": str(MANIFEST_PATH),
            "fonte": source_url,
            "data_descoberta": discovered_at,
            "catalogo_completo": bool(manifest.get("complete", False)),
            "total_manifestado": manifest.get("dataset_count", 0),
            "total_carregado": len(all_datasets),
        })

    st.divider()
    st.markdown("#### Exportação do recorte atual")
    exp1, exp2, exp3 = st.columns(3)
    exp1.download_button("Exportar conjuntos · CSV", filtered_datasets.to_csv(index=False).encode("utf-8-sig"),
                         "conjuntos_tse.csv", "text/csv", use_container_width=True)
    exp2.download_button("Exportar recursos · CSV", filtered_resources.to_csv(index=False).encode("utf-8-sig"),
                         "recursos_tse.csv", "text/csv", use_container_width=True)
    exp3.download_button("Exportar pacote · Excel", excel_bytes(filtered_datasets, filtered_resources),
                         "catalogo_tse.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         use_container_width=True)
    st.caption("NR TECH LAB · Brasil Eleitoral DataLab · Dados de origem: Tribunal Superior Eleitoral")


if __name__ == "__main__":
    main()
