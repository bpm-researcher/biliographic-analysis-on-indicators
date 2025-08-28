import streamlit as st
import pandas as pd
import numpy as np

def show():
    st.title("Performance Analysis")

    # Excel file upload
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

    if uploaded_file:
        # Load Excel file
        df = pd.read_excel(uploaded_file)

        # --- Total number of unique authors ---
        all_authors = df['Authors'].astype(str).str.split(',').explode().str.strip().unique()
        num_authors = len(all_authors)

        df_authors = df.assign(Authors=df['Authors'].astype(str).str.split(',')) \
                       .explode('Authors')
        df_authors['Authors'] = df_authors['Authors'].str.strip()

        # --- Total and average citations ---
        total_citations = df['Times Cited'].sum()
        avg_citations = df['Times Cited'].mean()

        # --- Display metrics ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Unique Authors", num_authors)
        col2.metric("Total Citations", int(total_citations))
        col3.metric("Average Citations", round(avg_citations, 2))

        # --- Functions to calculate h-index and g-index ---
        def h_index(citations):
            citations = sorted(citations, reverse=True)
            h = sum(c >= i + 1 for i, c in enumerate(citations))
            return h

        def g_index(citations):
            citations = sorted(citations, reverse=True)
            total = 0
            g = 0
            for i, c in enumerate(citations, start=1):
                total += c
                if total >= i**2:
                    g = i
            return g

        # --- Calculate metrics per author ---
        results = []
        for author, group in df_authors.groupby("Authors"):
            citations = group['Times Cited'].fillna(0).astype(int).tolist()
            results.append({
                "Author": author,
                "Number of Articles": len(citations),
                "Total Citations": sum(citations),
                "Average Citations": sum(citations) / len(citations) if citations else 0,
                "h-index": h_index(citations),
                "g-index": g_index(citations)
            })

        df_results = pd.DataFrame(results)

        # --- Main Results Table ---
        st.subheader("Author Metrics Table")
        st.dataframe(df_results)
        st.download_button("Download Author Metrics as CSV",
                           df_results.to_csv(index=False).encode("utf-8"),
                           "author_metrics.csv",
                           "text/csv")

        # --- Top 10 Rankings ---
        st.subheader("Top 10 Authors by Metric")

        col1, col2 = st.columns(2)

        # --- Total Citations ---
        with col1:
            st.markdown("**Top 10 by Total Citations**")
            top_total = df_results.sort_values("Total Citations", ascending=False).head(10)
            st.dataframe(top_total)
            st.download_button("Download CSV",
                               top_total.to_csv(index=False).encode("utf-8"),
                               "top10_total_citations.csv",
                               "text/csv")

            # --- Average Citations ---
            st.markdown("**Top 10 by Average Citations**")
            top_avg = df_results.sort_values("Average Citations", ascending=False).head(10)
            st.dataframe(top_avg)
            st.download_button("Download CSV",
                               top_avg.to_csv(index=False).encode("utf-8"),
                               "top10_avg_citations.csv",
                               "text/csv")

        # --- Number of Articles and h-index ---
        with col2:
            st.markdown("**Top 10 by Number of Articles**")
            top_articles = df_results.sort_values("Number of Articles", ascending=False).head(10)
            st.dataframe(top_articles)
            st.download_button("Download CSV",
                               top_articles.to_csv(index=False).encode("utf-8"),
                               "top10_articles.csv",
                               "text/csv")

            st.markdown("**Top 10 by h-index**")
            top_h = df_results.sort_values("h-index", ascending=False).head(10)
            st.dataframe(top_h)
            st.download_button("Download CSV",
                               top_h.to_csv(index=False).encode("utf-8"),
                               "top10_h_index.csv",
                               "text/csv")

        # --- g-index (separately displayed) ---
        st.markdown("**Top 10 by g-index**")
        top_g = df_results.sort_values("g-index", ascending=False).head(10)
        st.dataframe(top_g)
        st.download_button("Download CSV",
                           top_g.to_csv(index=False).encode("utf-8"),
                           "top10_g_index.csv",
                           "text/csv")

    else:
        st.warning("Please upload an Excel (.xlsx) file to continue.")
