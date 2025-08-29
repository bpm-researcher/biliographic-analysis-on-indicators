import streamlit as st
import pandas as pd
import itertools
from pyvis.network import Network
import streamlit.components.v1 as components
import networkx as nx
from networkx.algorithms import community

def show():
    st.title("Bibliometric Analysis - Co-Citation and Bibliographic Coupling")

    # File upload
    uploaded_file = st.file_uploader("Upload Excel file with columns 'Title' and 'Cited References'", type=["xlsx"])

    if uploaded_file:
        df = pd.read_excel(uploaded_file)

        # Clean references
        def clean_refs(refs):
            refs_list = [r.strip() for r in refs.split(';') if r.strip()]
            clean = []
            for r in refs_list:
                parts = r.split(',')
                if len(parts) >= 2:
                    ref_id = parts[0].strip() + " (" + parts[1].strip() + ")"
                    clean.append(ref_id)
                else:
                    clean.append(r)
            return clean

        # =====================
        # --- Co-Citation ---
        # =====================
        all_pairs = []
        for refs in df['Cited References'].dropna():
            refs_list = clean_refs(refs)
            for combo in itertools.combinations(sorted(set(refs_list)), 2):
                all_pairs.append(combo)

        pairs_df = pd.DataFrame(all_pairs, columns=['Ref1', 'Ref2'])
        co_citation_counts = pairs_df.value_counts().reset_index(name='Count')

        st.subheader("Top 20 Co-Citation Pairs")
        top20_df = co_citation_counts.sort_values("Count", ascending=False).head(20)
        st.dataframe(top20_df)
        csv_top20 = top20_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Top 20 Co-Citations as CSV", csv_top20, "top20_co_citation.csv", "text/csv")

        # Build graph
        top_pairs = co_citation_counts.sort_values("Count", ascending=False).head(100)
        G = nx.Graph()
        for _, row in top_pairs.iterrows():
            G.add_edge(row['Ref1'], row['Ref2'], weight=row['Count'])

        # Detect clusters
        clusters = community.greedy_modularity_communities(G)
        cluster_dict = {i+1: list(c) for i, c in enumerate(clusters)}

        # Cluster selection
        cluster_options = ["All"] + [f"Cluster {i}" for i in cluster_dict.keys()]
        selected_cluster = st.selectbox("Select Co-Citation Cluster", cluster_options)

        def get_gray_color(degree, max_degree):
            norm = degree / max_degree if max_degree > 0 else 0
            gray_value = int(200 * (1 - norm))
            return f"rgb({gray_value},{gray_value},{gray_value})"

        # Pyvis graph rendering
        G_vis = Network(height="600px", width="100%", notebook=False, bgcolor="#ffffff", font_color="black")
        nodes_to_show = G.nodes() if selected_cluster == "All" else cluster_dict[int(selected_cluster.split()[1])]
        max_degree = max([G.degree(node) for node in nodes_to_show])

        for node in nodes_to_show:
            degree = G.degree(node)
            G_vis.add_node(node, label=node, title=node, size=15 + degree*5, color=get_gray_color(degree, max_degree))

        for u, v, data in G.edges(data=True):
            if u in nodes_to_show and v in nodes_to_show:
                G_vis.add_edge(u, v, value=data['weight'])

        G_vis.save_graph("co_citation_cluster.html")
        with open("co_citation_cluster.html", 'r', encoding='utf-8') as f:
            HtmlFile = f.read()
        components.html(HtmlFile, height=600)
        st.download_button("Download Co-Citation Graph", HtmlFile, "co_citation_graph.html", "text/html")

        # Cluster summary
        st.subheader("Co-Citation Cluster Summary")
        cluster_summary = pd.DataFrame({
            "Cluster": cluster_dict.keys(),
            "Num_Nodes": [len(nodes) for nodes in cluster_dict.values()]
        })
        st.dataframe(cluster_summary)
        csv_clusters = cluster_summary.to_csv(index=False).encode("utf-8")
        st.download_button("Download Cluster Summary CSV", csv_clusters, "clusters_summary.csv", "text/csv")

        # =====================
        # --- Bibliographic Coupling ---
        # =====================
        st.subheader("Bibliographic Coupling with Clusters")

        pairs_bc = []
        refs_list = df['Cited References'].dropna().tolist()
        titles_list = df['Title'].dropna().tolist()

        for idx1, refs1 in enumerate(refs_list):
            refs1_set = set(clean_refs(refs1))
            for idx2 in range(idx1 + 1, len(refs_list)):
                refs2_set = set(clean_refs(refs_list[idx2]))
                shared_refs = refs1_set & refs2_set
                if shared_refs:
                    pairs_bc.append({
                        'Article1': titles_list[idx1],
                        'Article2': titles_list[idx2],
                        'Shared_Refs': len(shared_refs)
                    })

        bc_df = pd.DataFrame(pairs_bc).sort_values('Shared_Refs', ascending=False)
        top20_bc = bc_df.head(20)
        st.dataframe(top20_bc)
        csv_bc = top20_bc.to_csv(index=False).encode("utf-8")
        st.download_button("Download Top 20 Bibliographic Coupling", csv_bc, "top20_bibliographic_coupling.csv", "text/csv")

        # Build BC graph
        top_bc = bc_df.head(100)
        G_bc = nx.Graph()
        for _, row in top_bc.iterrows():
            G_bc.add_edge(row['Article1'], row['Article2'], weight=row['Shared_Refs'])

        # Detect clusters
        clusters_bc = community.greedy_modularity_communities(G_bc)
        cluster_dict_bc = {i+1: list(c) for i, c in enumerate(clusters_bc)}

        cluster_options_bc = ["All"] + [f"Cluster {i}" for i in cluster_dict_bc.keys()]
        selected_cluster_bc = st.selectbox("Select Bibliographic Coupling Cluster", cluster_options_bc)

        G_vis_bc = Network(height="600px", width="100%", notebook=False, bgcolor="#ffffff", font_color="black")
        nodes_to_show_bc = G_bc.nodes() if selected_cluster_bc == "All" else cluster_dict_bc[int(selected_cluster_bc.split()[1])]
        max_degree_bc = max([G_bc.degree(node) for node in nodes_to_show_bc])

        for node in nodes_to_show_bc:
            degree = G_bc.degree(node)
            G_vis_bc.add_node(node, label=node, title=node, size=15 + degree*5, color=get_gray_color(degree, max_degree_bc))

        for u, v, data in G_bc.edges(data=True):
            if u in nodes_to_show_bc and v in nodes_to_show_bc:
                G_vis_bc.add_edge(u, v, value=data['weight'])

        G_vis_bc.save_graph("bibliographic_coupling_cluster.html")
        with open("bibliographic_coupling_cluster.html", 'r', encoding='utf-8') as f:
            HtmlFile_bc = f.read()
        components.html(HtmlFile_bc, height=600)
        st.download_button("Download Bibliographic Coupling Graph", HtmlFile_bc, "bibliographic_coupling_clusters.html", "text/html")

        # BC cluster summary
        st.subheader("Bibliographic Coupling Cluster Summary")
        cluster_summary_bc = pd.DataFrame({
            "Cluster": cluster_dict_bc.keys(),
            "Num_Nodes": [len(nodes) for nodes in cluster_dict_bc.values()]
        })
        st.dataframe(cluster_summary_bc)
        csv_clusters_bc = cluster_summary_bc.to_csv(index=False).encode("utf-8")
        st.download_button("Download BC Cluster Summary CSV", csv_clusters_bc, "clusters_bc_summary.csv", "text/csv")

    else:
        st.info("Please upload an Excel (.xlsx) file with 'Title' and 'Cited References' columns.")
