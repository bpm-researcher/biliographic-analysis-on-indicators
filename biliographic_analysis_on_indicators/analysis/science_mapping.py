import itertools
import json                      #  ← NEW
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Optional

import networkx as nx
import nltk
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from networkx.algorithms import community
from networkx.exception import PowerIterationFailedConvergence
from nltk.corpus import stopwords
from pyvis.network import Network

# ─────────────────────────────────────────────────────────────────────────────
#  Constants / styling  –– LIGHT THEME
# ─────────────────────────────────────────────────────────────────────────────
BG_COLOR    = "#ffffff"   # white background
FONT_COLOR  = "#000000"   # black text
EDGE_COLOR  = "#cccccc"   # light-grey edges
HIGHLIGHT   = "#ff9900"   # orange for hover / selection


# ─────────────────────────────────────────────────────────────────────────────
#  Helper to create a pre-configured PyVis network
# ─────────────────────────────────────────────────────────────────────────────
def make_network(height: str = "600px", width: str = "100%") -> Network:
    """
    Return a pyvis.Network already configured with a light colour theme and
    safe (JSON-validated) options.
    """
    vis = Network(height=height, width=width,
                  bgcolor=BG_COLOR, font_color=FONT_COLOR)

    options_dict = {
       "nodes": {
    "font": {
        "color": "#000000",
        "size": 32,             # <<< MAKE LABELS LARGE
        "face": "arial",
        "vadjust": -10          # <<< PULL LABEL UPWARD
    },
    "shape": "dot",
    "scaling": {"label": True},
    "color": {
        "border": EDGE_COLOR,
        "background": BG_COLOR,
        "highlight": {"border": HIGHLIGHT, "background": BG_COLOR},
    },

        },
        "edges": {
            "color": {
                "color": EDGE_COLOR,
                "highlight": HIGHLIGHT,
                "inherit": False,
            },
            "smooth": {"enabled": True, "type": "dynamic"},
        },
        "interaction": {"hover": True},
        "physics": {
    "enabled": True,
    "barnesHut": {
        "gravitationalConstant": -2000,
        "centralGravity": 0.3,
        "springLength": 150,
        "springConstant": 0.04,
        "avoidOverlap": 0.1
    }
},
    }

    # Use json.dumps so the string handed to pyvis is always valid JSON
    vis.set_options(json.dumps(options_dict))
    return vis


# ─────────────────────────────────────────────────────────────────────────────
#  Streamlit entry point
# ─────────────────────────────────────────────────────────────────────────────
def show():
    st.title("📊 Science Mapping Dashboard")

    df = upload_file("science")
    if df is None:
        st.info("Please upload a file to use this section.")
        return

    display_reference_summary(df)
    display_cocitation_analysis(df)
    display_bibliographic_coupling_analysis(df)
    display_coword_analysis(df)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers (generic)
# ─────────────────────────────────────────────────────────────────────────────
def safe_download(component_fn, *args, **kwargs):
    """Wrap streamlit.download_button to avoid duplicate-key / empty-data errors."""
    try:
        component_fn(*args, **kwargs)
    except (ValueError, st.errors.StreamlitAPIException):
        st.warning("Nothing to download yet (or duplicate key).")


def html_to_pdf_bytes(html_string: str) -> Optional[bytes]:
    """
    Convert a PyVis HTML string to PDF.
    Returns the PDF as bytes if WeasyPrint (and its native libraries) can be
    imported; otherwise returns None and shows a one-time notice.
    """
    try:
        from weasyprint import HTML  # late import
    except Exception as exc:
        if "weasyprint_warned" not in st.session_state:
            st.session_state["weasyprint_warned"] = True
            st.info(
                "PDF generation is not available on this system "
                f"(WeasyPrint could not be loaded: {exc})."
            )
        return None

    buf = BytesIO()
    HTML(string=html_string, base_url=".").write_pdf(buf)
    buf.seek(0)
    return buf.read()


def get_orange_color(value: float, max_value: float) -> str:
    norm = value / max_value if max_value else 0
    return f"rgb(255,{int(200 - 100 * norm)},{int(100 * (1 - norm))})"


def clean_refs(refs) -> list:
    try:
        if pd.isna(refs):
            return []
        refs_list = [r.strip() for r in refs.split(";") if r.strip()]
        valid = []
        for r in refs_list:
            if (
                (any(c.isalpha() for c in r) and " " in r)
                or r.lower().startswith("10.")
                or "doi.org" in r.lower()
            ):
                valid.append(r)
        return valid
    except Exception as exc:
        st.warning(f"Could not parse references: {exc}")
        return []


def upload_file(key):
    uploaded_file = st.file_uploader(
        "Upload Excel file with columns 'Title', 'Article References', and 'Abstract'",
        type=["xlsx"],
        key=key,
    )

    if uploaded_file is None:
        return None

    try:
        df = pd.read_excel(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read the Excel file: {exc}")
        return None

    expected = {"Title", "Article References", "Abstract"}
    missing = expected - set(df.columns)
    if missing:
        st.error("Missing column(s): " + ", ".join(missing))
        return None

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  Reference summary
# ─────────────────────────────────────────────────────────────────────────────
def display_reference_summary(df):
    if "Article References" not in df.columns:
        return

    st.subheader("Reference Summary")

    total_refs = sum(len(clean_refs(r)) for r in df["Article References"].dropna())
    articles_with_refs = df["Article References"].notna().sum()
    articles_missing_refs = df["Article References"].isna().sum()
    total_articles = len(df)

    cols = st.columns(4)
    cols[0].metric("Total References Found", total_refs)
    cols[1].metric("Articles with References", articles_with_refs)
    cols[2].metric("Articles Missing References", articles_missing_refs)
    cols[3].metric(
        "Percentage Missing",
        f"{articles_missing_refs/total_articles*100:.2f}%",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Co-Citation analysis
# ─────────────────────────────────────────────────────────────────────────────
def display_cocitation_analysis(df):
    if df["Article References"].dropna().empty:
        return

    pairs_df = co_citation_pairs_df(df)
    co_citation_counts = pairs_df.value_counts().reset_index(name="Count")
    if co_citation_counts.empty:
        return

    st.subheader("Co-Citation Analysis")
    display_top_20_cocitation_pairs_table(co_citation_counts)

    G = co_citation_graph(co_citation_counts)
    if not G:
        return

    cluster_dict, metric_choice = cluster_and_metric_selection(G, "cocitation")
    html_graph = display_selected_cluster(
        select_cluster_option(cluster_dict, "cocitation"),
        cluster_dict,
        G,
        metric_choice,
    )
    if html_graph:
        safe_download(
            st.download_button,
            "Download Co-Citation Graph (HTML)",
            html_graph,
            "co_citation_graph.html",
            "text/html",
            key="cocitation_html",
        )
        pdf_bytes = html_to_pdf_bytes(html_graph)
        if pdf_bytes:
            safe_download(
                st.download_button,
                "Download Co-Citation Graph (PDF)",
                pdf_bytes,
                "co_citation_graph.pdf",
                "application/pdf",
                key="cocitation_pdf",
            )


def co_citation_pairs_df(df):
    all_pairs = []
    for refs in df["Article References"].dropna():
        rlist = list(set(clean_refs(refs)))
        for combo in itertools.combinations(sorted(rlist), 2):
            all_pairs.append(combo)
    return pd.DataFrame(all_pairs, columns=["Ref1", "Ref2"])


def co_citation_graph(counts_df):
    top_pairs = counts_df.sort_values("Count", ascending=False).head(100)
    G = nx.Graph()
    for _, row in top_pairs.iterrows():
        G.add_edge(row["Ref1"], row["Ref2"], weight=row["Count"])
    return G


def display_top_20_cocitation_pairs_table(co_citation_counts):
    top20 = co_citation_counts.sort_values("Count", ascending=False).head(20)
    st.markdown("Top 20 Co-Citation Pairs")
    st.dataframe(top20, use_container_width=True)
    safe_download(
        st.download_button,
        "Download CSV",
        top20.to_csv(index=False).encode(),
        "top20_cocitation.csv",
        "text/csv",
        key="top20_cocitation",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Bibliographic Coupling analysis
# ─────────────────────────────────────────────────────────────────────────────
def display_bibliographic_coupling_analysis(df):
    if df["Article References"].dropna().empty:
        return

    bc_pairs_df = bibliographic_coupling_pairs(df)
    if bc_pairs_df.empty:
        return

    st.subheader("Bibliographic Coupling Analysis")
    display_top_20_bc_pairs_table(bc_pairs_df)

    G = bc_graph(bc_pairs_df)
    if not G:
        return

    cluster_dict, metric_choice = cluster_and_metric_selection(G, "bc")
    html_graph = display_selected_cluster(
        select_cluster_option(cluster_dict, "bc"), cluster_dict, G, metric_choice
    )
    if html_graph:
        safe_download(
            st.download_button,
            "Download Bibliographic Coupling Graph (HTML)",
            html_graph,
            "bibliographic_coupling_graph.html",
            "text/html",
            key="bc_html",
        )
        pdf_bytes = html_to_pdf_bytes(html_graph)
        if pdf_bytes:
            safe_download(
                st.download_button,
                "Download Bibliographic Coupling Graph (PDF)",
                pdf_bytes,
                "bibliographic_coupling_graph.pdf",
                "application/pdf",
                key="bc_pdf",
            )


def bibliographic_coupling_pairs(df):
    pairs = []
    refs_list = df["Article References"].dropna().tolist()
    titles = df["Title"].fillna("Untitled").tolist()

    for i, refs1 in enumerate(refs_list):
        refs_set = set(clean_refs(refs1))
        for j in range(i + 1, len(refs_list)):
            shared = refs_set & set(clean_refs(refs_list[j]))
            if shared:
                pairs.append(
                    {
                        "Article1": titles[i],
                        "Article2": titles[j],
                        "Shared_Refs": len(shared),
                    }
                )
    return pd.DataFrame(pairs).sort_values("Shared_Refs", ascending=False)


def bc_graph(bc_df):
    top_bc = bc_df.head(100)
    G = nx.Graph()
    for _, row in top_bc.iterrows():
        G.add_edge(row["Article1"], row["Article2"], weight=row["Shared_Refs"])
    return G


def display_top_20_bc_pairs_table(bc_df):
    top20 = bc_df.head(20)
    st.markdown("Top 20 Bibliographic-Coupling Pairs")
    st.dataframe(top20, use_container_width=True)
    safe_download(
        st.download_button,
        "Download CSV",
        top20.to_csv(index=False).encode(),
        "top20_bibliographic_coupling.csv",
        "text/csv",
        key="top20_bc",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Co-Word analysis
# ─────────────────────────────────────────────────────────────────────────────
def display_coword_analysis(df):
    st.subheader("Co-Word Analysis (Focus Word)")

    focus_word = st.text_input("Focus word", value="future").lower()
    fields = st.multiselect(
        "Fields to include", ["Title", "Abstract"], default=["Title", "Abstract"]
    )
    top_n = st.slider("Top N co-words to display", 5, 100, 20, step=5)

    if not focus_word or not fields:
        return

    display_coword_graph(focus_word, fields, df, top_n)


def display_coword_graph(focus_word, fields, df, top_n):
    # Ensure NLTK stopwords are present
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords")

    stop_words = set(stopwords.words("english"))

    text_series = df[fields].fillna("").agg(" ".join, axis=1).str.lower()
    subset = text_series[text_series.str.contains(focus_word, regex=False)]
    if subset.empty:
        st.info(f"No occurrences of '{focus_word}'.")
        return

    token_lists = [
        [w for w in txt.split() if w.isalpha() and w not in stop_words] for txt in subset
    ]

    counter = Counter()
    for tokens in token_lists:
        counter.update(set(tokens) - {focus_word})

    if not counter:
        return

    top_words = dict(counter.most_common(top_n))

    # Build graph
    G = nx.Graph()
    G.add_node(focus_word, size=30)
    for w, cnt in top_words.items():
        G.add_node(w, size=10 + cnt)
        G.add_edge(focus_word, w, weight=cnt)

    # Visualise with PyVis
    vis = make_network()
    for node in G.nodes():
        vis.add_node(
    node,
    label=nodenum,
    title=f"{node}\n{metric}: {val:.4f}",
    size=15 + 40 * (val / max_val if max_val else 0),
    color=get_orange_color(val, max_val),
    group=cid,
    font={"size": 28, "color": "#000000"},   # <<< FORCE READABLE LABELS
)
    for u, v, d in G.edges(data=True):
        vis.add_edge(u, v, value=d["weight"])

    html_path = Path("coword.html")
    vis.save_graph(str(html_path))
    html = html_path.read_text(encoding="utf-8")

    components.html(html, height=600)

    safe_download(
        st.download_button,
        "Download Co-Word Graph (HTML)",
        html,
        "co_word_graph.html",
        "text/html",
        key="coword_html",
    )
    pdf_bytes = html_to_pdf_bytes(html)
    if pdf_bytes:
        safe_download(
            st.download_button,
            "Download Co-Word Graph (PDF)",
            pdf_bytes,
            "co_word_graph.pdf",
            "application/pdf",
            key="coword_pdf",
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Cluster handling + metrics
# ─────────────────────────────────────────────────────────────────────────────
def cluster_and_metric_selection(G, key_prefix=""):
    algo = st.selectbox(
        "Clustering algorithm",
        ["Greedy", "Louvain", "Label Propagation"],
        key=f"{key_prefix}_algo",
    )
    clusters = run_clustering(G, algo)
    cluster_dict = {i + 1: list(c) for i, c in enumerate(clusters)}

    metric = st.selectbox(
        "Centrality metric",
        ["Degree", "Betweenness", "Eigenvector", "Closeness", "PageRank"],
        key=f"{key_prefix}_metric",
    )
    return cluster_dict, metric


def run_clustering(G, algo="Greedy"):
    if algo == "Greedy":
        return community.greedy_modularity_communities(G)
    if algo == "Label Propagation":
        return community.asyn_lpa_communities(G)
    if algo == "Louvain":
        try:
            import community as community_louvain
        except ImportError:
            st.error("Install python-louvain:  pip install python-louvain")
            return []
        part = community_louvain.best_partition(G)
        clusters = {}
        for n, cid in part.items():
            clusters.setdefault(cid, []).append(n)
        return [set(c) for c in clusters.values()]
    return []


def calculate_all_metrics(G):
    with st.spinner("Calculating centrality…"):
        try:
            degree = dict(G.degree())
            betw = nx.betweenness_centrality(G, weight="weight", normalized=True)
            eig = nx.eigenvector_centrality(G, weight="weight", max_iter=1000)
            clos = nx.closeness_centrality(G)
            pr = nx.pagerank(G, weight="weight")
        except PowerIterationFailedConvergence:
            st.warning("Eigenvector centrality did not converge (set to 0).")
            eig = {n: 0 for n in G.nodes()}
            pr = nx.pagerank(G, weight="weight")
            degree = dict(G.degree())
            betw = nx.betweenness_centrality(G, weight="weight", normalized=True)
            clos = nx.closeness_centrality(G)

    return {
        "Degree": degree,
        "Betweenness": betw,
        "Eigenvector": eig,
        "Closeness": clos,
        "PageRank": pr,
    }


def select_cluster_option(cluster_dict, key_prefix=""):
    opts = ["All"] + [f"Cluster {i}" for i in cluster_dict]
    return st.selectbox("Which cluster?", opts, key=f"{key_prefix}_cluster")


def display_selected_cluster(selected, cluster_dict, G, metric="Degree"):
    metrics = calculate_all_metrics(G)
    values = metrics[metric]

    # If showing ALL clusters, create a larger canvas so exported HTML/PDF
    # is higher resolution and readable when printed in an appendix.
    if selected == "All":
        vis = make_network(height="2000px", width="3000px")
    else:
        vis = make_network()

    nodes_to_show = (
        G.nodes() if selected == "All" else cluster_dict[int(selected.split()[1])]
    )

    max_val = max((values.get(n, 0) for n in nodes_to_show), default=1)
    legend = []

    for cid, nodes in cluster_dict.items():
        if selected != "All" and cid != int(selected.split()[1]):
            continue
        for i, node in enumerate(
            sorted(nodes, key=lambda n: values.get(n, 0), reverse=True), 1
        ):
            nodenum = f"{cid}-{i}"
            val = values.get(node, 0)
            legend.append(
                {
                    "Node": nodenum,
                    "Reference": node,
                    "Cluster": cid,
                    metric: round(val, 4),
                }
            )
            # label is the nodenum; title remains the full reference (tooltip)
            vis.add_node(
                node,
                label=nodenum,
                title=f"{node}\n{metric}: {val:.4f}",
                size=15 + 40 * (val / max_val if max_val else 0),
                color=get_orange_color(val, max_val),
                group=cid,
            )

    for u, v, d in G.edges(data=True):
        if u in nodes_to_show and v in nodes_to_show:
            vis.add_edge(u, v, value=d["weight"])

    html_path = Path("cluster.html")
    vis.save_graph(str(html_path))
    html = html_path.read_text(encoding="utf-8")

    # Show graph in-streamlit
    components.html(html, height=800 if selected != "All" else 900)

    # Show legend and allow download
    st.markdown("Legend")
    st.dataframe(pd.DataFrame(legend), use_container_width=True)
    return html
