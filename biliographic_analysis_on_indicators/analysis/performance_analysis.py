import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from typing import Callable, Any, Optional, List, Union
import uuid

# ─────────────────────────────────────────────────────────────────────────────
#  Matplotlib theme switcher
# ─────────────────────────────────────────────────────────────────────────────
THEMES = {
    "Light (default)": "default",          # Matplotlib’s default (light) theme
    "Dark": "dark_background",             # Matplotlib’s built-in dark theme
}

# Sidebar radio button lets the user pick a theme.
chosen_theme = st.sidebar.radio("🎨 Plot theme", list(THEMES.keys()), index=0)

# Apply the chosen theme *before* any figure is created.
plt.style.use(THEMES[chosen_theme])

# Streamlit: turn off the full tracebacks for cleaner appearance.
st.set_option("client.showErrorDetails", False)

# ───────────────────────────────────────────────────────────────
# Helper to display a Matplotlib figure + PDF download button
# ───────────────────────────────────────────────────────────────
def show_fig_with_download(
    fig: plt.Figure,
    file_name: str,
    caption: Optional[str] = None
):
    """
    Show *fig* in Streamlit and offer it as a vector-PDF download.
    """
    st.pyplot(fig)

    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", bbox_inches="tight")
    buf.seek(0)

    st.download_button(
        label="⬇ Download as PDF",
        data=buf,
        file_name=file_name,
        mime="application/pdf",
    )


def show():
    st.title("Performance Analysis")

    df = upload_file("performance")
    if df is None:
        return

    display(df)


# ─────────────────────────────────────────────────────────────────────────────
#                               HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def safe_run(func: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as err:
            st.error(f"[{func.__name__}] Missing column: {err}")
        except ZeroDivisionError:
            st.error(f"[{func.__name__}] Division by zero.")
        except ValueError as err:
            st.error(f"[{func.__name__}] Value error: {err}")
        except Exception as err:
            st.error(f"[{func.__name__}] Unexpected error:")
            st.exception(err)
    return wrapper


def upload_file(key: str = "performance") -> Optional[pd.DataFrame]:
    uploaded_file = st.file_uploader(
        "Upload Excel file (expected columns: "
        "'Authors', 'Title', 'Times Cited', 'Publication year')",
        type=["xlsx", "xls"],
        key=key,
    )

    if uploaded_file is None:
        st.info("Please upload an Excel file to continue.")
        return None

    try:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception as exc:
        st.error(f"Could not read the Excel file – {exc}")
        return None

    expected = {"Authors", "Title", "Times Cited", "Publication year"}
    missing = expected - set(df.columns)
    if missing:
        st.error("Missing column(s): " + ", ".join(missing))
        return None

    numeric_cols = ["Times Cited", "Publication year"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def h_index(citations: List[Union[int, float, None]]) -> int:
    try:
        citations = [int(c) for c in citations if pd.notna(c)]
    except Exception:
        return 0
    citations.sort(reverse=True)
    return sum(c >= i + 1 for i, c in enumerate(citations))


def g_index(citations: List[Union[int, float, None]]) -> int:
    try:
        citations = [int(c) for c in citations if pd.notna(c)]
    except Exception:
        return 0
    citations.sort(reverse=True)
    total = 0
    g = 0
    for i, c in enumerate(citations, start=1):
        total += c
        if total >= i ** 2:
            g = i
    return g


# ─────────────────────────────────────────────────────────────────────────────
#                            MAIN DISPLAY
# ─────────────────────────────────────────────────────────────────────────────
@safe_run
def display(df: pd.DataFrame):
    if df.empty:
        st.warning("The uploaded data set is empty.")
        return

    display_header_data(df)

    if "Authors" not in df.columns or df["Authors"].dropna().empty:
        st.warning("No author information available.")
        return

    df_authors = df.assign(Authors=df["Authors"].astype(str).str.split(",")).explode(
        "Authors"
    )
    df_authors["Authors"] = df_authors["Authors"].str.strip()

    df_results = calculate_metrics_per_author(df_authors)

    display_top_10_tables(df_results)
    display_most_cited_per_year_graph(df)
    display_authors_with_more_citations(df_results, df)
    display_gini_and_lorenz(df_results)
    display_paper_level_gini_and_lorenz(df)
    display_citation_data_per_year(df)
    display_articles_per_year(df)          # ← modified inside this function
    display_papers_over_100(df)
    display_citation_tiers(df)
    display_error_info(df)


# ─────────────────────────────────────────────────────────────────────────────
#                       INDIVIDUAL DISPLAY SECTIONS
# ─────────────────────────────────────────────────────────────────────────────
@safe_run
def display_header_data(df: pd.DataFrame):
    all_authors = (
        df["Authors"].astype(str).str.split(",").explode().str.strip().unique()
    )
    num_authors = len(all_authors)

    total_citations = df["Times Cited"].sum(skipna=True)
    avg_citations = df["Times Cited"].mean(skipna=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Unique Authors", num_authors)
    col2.metric("Total Citations", int(total_citations))
    col3.metric("Average Citations", round(avg_citations, 2))

@safe_run
def display_paper_level_gini_and_lorenz(df: pd.DataFrame):
    """
    Lorenz curve + Gini coefficient for the distribution of citations
    across individual papers (NOT authors).
    """
    st.subheader("Lorenz Curve of Citations Across Papers")

    if df.empty or "Times Cited" not in df.columns:
        st.info("No citation data available.")
        return

    # Keep only finite, non-NaN citation counts; treat NaN as 0
    citations = df["Times Cited"].fillna(0).astype(int).values
    if citations.size == 0 or citations.sum() == 0:
        st.info("All papers have zero citations.")
        return

    sorted_cit = np.sort(citations)                    # ascending
    cum_cit    = np.cumsum(sorted_cit) / sorted_cit.sum()
    n          = len(sorted_cit)
    x_axis     = np.arange(1, n + 1) / n

    # Plot
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x_axis, cum_cit, label="Lorenz Curve", color="steelblue")
    ax.plot([0, 1], [0, 1], "--", color="grey", label="Equality Line")
    ax.set_xlabel("Cumulative Share of Papers")
    ax.set_ylabel("Cumulative Share of Citations")
    ax.set_title("Lorenz Curve – Citations per Paper")
    ax.legend()
    show_fig_with_download(fig, "lorenz_curve_papers.pdf")

    # Gini coefficient
    cumulative_sum = np.cumsum(sorted_cit)
    gini = (n + 1 - 2 * np.sum(cumulative_sum) / cumulative_sum[-1]) / n
    st.markdown(f"**Gini Coefficient (paper level):** `{gini:.3f}`")


@safe_run
def calculate_metrics_per_author(df_authors: pd.DataFrame) -> pd.DataFrame:
    results = []
    for author, group in df_authors.groupby("Authors"):
        citations = group["Times Cited"].fillna(0).astype(int).tolist()
        num_articles = len(citations)

        results.append(
            {
                "Author": author,
                "Number of Articles": num_articles,
                "Total Citations": sum(citations),
                "Average Citations": sum(citations) / num_articles if num_articles else 0,
                "h-index": h_index(citations),
                "g-index": g_index(citations),
            }
        )

    return pd.DataFrame(results)


@safe_run
def display_top_10_tables(df_results: pd.DataFrame):
    if df_results.empty:
        st.info("No author results to show.")
        return

    st.subheader("Top 10 Authors by Metric")
    col1, col2 = st.columns(2)
    _display_citations(col1, df_results)
    _display_number_and_index(col2, df_results)
    _display_g_index(df_results)


def _download_button(
    df: pd.DataFrame, label: str, file_name: str, key: Optional[str] = None
):
    unique_key = key or f"{file_name}_{uuid.uuid4().hex[:6]}"
    st.download_button(
        label, df.to_csv(index=False).encode("utf-8"), file_name, "text/csv", key=unique_key
    )


def _display_citations(col, df_results):
    with col:
        st.markdown("**Top 10 by Total Citations**")
        top_total = df_results.nlargest(10, "Total Citations")
        st.dataframe(top_total)
        _download_button(top_total, "Download CSV", "top10_total_citations.csv")

        st.markdown("**Top 10 by Average Citations**")
        top_avg = df_results.nlargest(10, "Average Citations")
        st.dataframe(top_avg)
        _download_button(top_avg, "Download CSV", "top10_avg_citations.csv")


def _display_number_and_index(col, df_results):
    with col:
        st.markdown("**Top 10 by Number of Articles**")
        top_articles = df_results.nlargest(10, "Number of Articles")
        st.dataframe(top_articles)
        _download_button(top_articles, "Download CSV", "top10_articles.csv")

        st.markdown("**Top 10 by h-index**")
        top_h = df_results.nlargest(10, "h-index")
        st.dataframe(top_h)
        _download_button(top_h, "Download CSV", "top10_h_index.csv")


def _display_g_index(df_results):
    st.markdown("**Top 10 by g-index**")
    top_g = df_results.nlargest(10, "g-index")
    st.dataframe(top_g)
    _download_button(top_g, "Download CSV", "top10_g_index.csv")


@safe_run
def display_most_cited_per_year_graph(df: pd.DataFrame, min_cit: int = 100):
    if df.empty:
        st.info("Dataset is empty – nothing to plot.")
        return

    needed = {"Times Cited", "Publication year", "Title"}
    if needed - set(df.columns):
        st.warning("Required columns missing for this plot.")
        return

    st.subheader(f"Most Cited Articles per Year (Citations > {min_cit})")
    high_cited = df[df["Times Cited"] > min_cit][
        ["Title", "Publication year", "Times Cited"]
    ]

    if high_cited.empty:
        st.info(f"No articles with more than {min_cit} citations found.")
        return

    high_cited = high_cited.sort_values(
        ["Publication year", "Times Cited"], ascending=[True, False]
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    for year, group in high_cited.groupby("Publication year"):
        ax.bar(group["Title"], group["Times Cited"], label=year)

    ax.set_xlabel("Article Title")
    ax.set_ylabel("Times Cited")
    ax.set_title(f"Most Cited Articles per Year (Citations > {min_cit})")
    ax.legend(title="Publication Year")
    plt.xticks(rotation=90)

    show_fig_with_download(fig, "most_cited_per_year.pdf")
    st.dataframe(high_cited)
    _download_button(
        high_cited,
        f"Download Most Cited Articles (>{min_cit})",
        "most_cited_articles_per_year.csv",
    )


@safe_run
def display_authors_with_more_citations(df_results: pd.DataFrame, df: pd.DataFrame):
    st.subheader("Authors with More Than 100 Total Citations")
    authors_over_100 = df_results[df_results["Total Citations"] > 100].sort_values(
        "Total Citations", ascending=False
    )

    if authors_over_100.empty:
        st.info("No authors with more than 100 citations found.")
    else:
        st.dataframe(authors_over_100)
        _download_button(authors_over_100, "Download CSV", "authors_over_100.csv")

    st.subheader("Number of Citations per Year")

    if "Publication year" not in df.columns:
        st.warning("No 'Publication year' column in the dataset.")
        return

    citations_per_year = (
        df.dropna(subset=["Publication year"])
        .groupby("Publication year")["Times Cited"]
        .sum()
        .astype(int)
        .sort_index()
    )

    citations_per_year = citations_per_year[citations_per_year.index >= 1962]

    if citations_per_year.empty:
        st.info("No citation information available (≥ 1962).")
        return

    start_year = 1962
    end_year = citations_per_year.index.max()
    full_years = np.arange(start_year, end_year + 1)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(
        citations_per_year.index,
        citations_per_year.values,
        marker="o",
        linestyle="-",
        color="steelblue",
    )

    ax.set_xticks(full_years)
    ax.set_xticklabels(full_years, rotation=90)

    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Number of Citations")
    ax.set_title("Number of Citations per Year (≥ 1962)")
    ax.grid(False)

    show_fig_with_download(fig, "citations_per_year.pdf")

    cit_table = citations_per_year.reindex(full_years, fill_value=0).reset_index()
    cit_table.columns = ["Publication Year", "Number of Citations"]
    st.dataframe(cit_table)
    _download_button(cit_table, "Download CSV", "citations_per_year.csv")


@safe_run
def display_gini_and_lorenz(df_results: pd.DataFrame):
    st.subheader("Lorenz Curve of Citations Across Authors")

    if df_results.empty:
        st.info("No author data to compute Gini coefficient.")
        return

    sorted_citations = np.sort(df_results["Total Citations"].values)
    if sorted_citations[-1] == 0:
        st.info("All authors have zero citations.")
        return

    cumulative_citations = np.cumsum(sorted_citations) / sorted_citations.sum()
    x_axis = np.arange(1, len(sorted_citations) + 1) / len(sorted_citations)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x_axis, cumulative_citations, label="Lorenz Curve", color="steelblue")
    ax.plot([0, 1], [0, 1], "--", color="black", label="Equality Line")
    ax.set_xlabel("Cumulative Share of Authors")
    ax.set_ylabel("Cumulative Share of Citations")
    ax.set_title("Lorenz Curve of Citations")
    ax.legend()
    show_fig_with_download(fig, "lorenz_curve.pdf")

    n = len(sorted_citations)
    cumulative_sum = np.cumsum(sorted_citations)
    gini = (n + 1 - 2 * np.sum(cumulative_sum) / cumulative_sum[-1]) / n
    st.markdown(f"**Gini Coefficient of Citations:** {gini:.3f}")


@safe_run
def display_citation_data_per_year(df: pd.DataFrame):
    st.subheader("Publications vs Citations per Year")

    if "Publication year" not in df.columns:
        st.warning("No 'Publication year' column found.")
        return

    df_year = df.dropna(subset=["Publication year"]).copy()
    df_year["Publication year"] = df_year["Publication year"].astype(int)

    if df_year.empty:
        st.info("No valid publication year data.")
        return

    pubs_per_year = df_year.groupby("Publication year").size()
    citations_per_year = df_year.groupby("Publication year")["Times Cited"].sum()
    citations_per_year = citations_per_year[citations_per_year.index >= 1962]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(pubs_per_year.index, pubs_per_year.values, marker="o", label="Publications")
    ax.plot(
        citations_per_year.index,
        citations_per_year.values,
        marker="s",
        label="Citations",
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("Count")
    ax.set_title("Publications and Citations per Year")
    ax.legend()
    show_fig_with_download(fig, "pubs_vs_citations_per_year.pdf")

    _display_average_citation_year(citations_per_year, pubs_per_year)


# ─────────────────────────────────────────────────────────────────────────────
# Articles-per-year line chart (≥ 1962) – now 5-year tick interval
# ─────────────────────────────────────────────────────────────────────────────
@safe_run
def display_articles_per_year(df: pd.DataFrame):
    """
    Show a line graph and table of the number of articles published
    each year starting from 1962.

    CHANGE:  x-axis ticks every 5 years (instead of every year / 10 years).
    """
    st.subheader("Articles Published per Year (≥ 1962)")

    if "Publication year" not in df.columns:
        st.warning("No 'Publication year' column found.")
        return

    df_year = df.dropna(subset=["Publication year"]).copy()
    df_year["Publication year"] = df_year["Publication year"].astype(int)

    if df_year.empty:
        st.info("No valid publication year data.")
        return

    pubs_per_year = df_year.groupby("Publication year").size()
    pubs_per_year = pubs_per_year[pubs_per_year.index >= 1962]

    if pubs_per_year.empty:
        st.info("No publications from 1962 onwards.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(
        pubs_per_year.index,
        pubs_per_year.values,
        marker="o",
        linestyle="-",
        color="steelblue",
    )

    # ---- 5-year tick interval ------------------------------------------------
    start_year = int(pubs_per_year.index.min())
    end_year   = int(pubs_per_year.index.max())
    first_tick = start_year - (start_year % 5)  # align to nearest multiple of 5
    five_year_ticks = np.arange(first_tick, end_year + 1, 5)

    ax.set_xticks(five_year_ticks)
    ax.set_xticklabels(five_year_ticks, rotation=90)
    # --------------------------------------------------------------------------

    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Number of Articles")
    ax.set_title("Articles Published per Year (≥ 1962)")
    ax.grid(False)

    show_fig_with_download(fig, "articles_per_year.pdf")

    pubs_table = pubs_per_year.reset_index()
    pubs_table.columns = ["Publication Year", "Number of Articles"]
    st.dataframe(pubs_table)
    _download_button(pubs_table, "Download CSV", "articles_per_year.csv")


# ─────────────────────────────────────────────────────────────────────────────
# Papers over 100 citations & Citation-tier summary
# ─────────────────────────────────────────────────────────────────────────────
@safe_run
def display_papers_over_100(df: pd.DataFrame):
    """Show every paper that has more than 100 citations."""
    st.subheader("Papers with More Than 100 Citations")

    if "Times Cited" not in df.columns:
        st.warning("Column 'Times Cited' is missing.")
        return

    papers_100 = df[df["Times Cited"] > 100].copy()
    papers_100 = papers_100.sort_values("Times Cited", ascending=False)

    if papers_100.empty:
        st.info("No papers with more than 100 citations were found.")
        return

    st.dataframe(papers_100)
    _download_button(
        papers_100,
        "Download CSV",
        "papers_over_100_citations.csv",
    )


@safe_run
def display_citation_tiers(df: pd.DataFrame):
    """
    Produce a summary table with the number of papers that fall
    into a set of citation ranges.
    """
    st.subheader("Number of Papers per Citation Range")

    if "Times Cited" not in df.columns:
        st.warning("Column 'Times Cited' is missing.")
        return

    bins = [-np.inf, 10, 50, 100, 300, 500, 600, np.inf]
    labels = [
        "Under 10 citations",
        "10 – 50 citations",
        "50 – 100 citations",
        "100 – 300 citations",
        "300 – 500 citations",
        "500 – 600 citations",
        "Over 600 citations",
    ]

    df_tier = df.copy()
    df_tier["Citation Range"] = pd.cut(
        df_tier["Times Cited"], bins=bins, labels=labels, right=False
    )

    tier_counts = (
        df_tier.groupby("Citation Range")
        .size()
        .reindex(labels)
        .fillna(0)
        .astype(int)
        .reset_index(name="Number of Papers")
    )

    st.dataframe(tier_counts)
    _download_button(
        tier_counts,
        "Download CSV",
        "citation_tiers_summary.csv",
    )


@safe_run
def _display_average_citation_year(citations_per_year, pubs_per_year):
    st.subheader("Average Citations per Paper per Year")

    with np.errstate(divide="ignore", invalid="ignore"):
        avg_citations_per_year = citations_per_year / pubs_per_year
        avg_citations_per_year.replace([np.inf, -np.inf], np.nan, inplace=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(
        avg_citations_per_year.index,
        avg_citations_per_year.values,
        marker="o",
        color="steelblue",
    )
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Average Citations per Paper")
    ax.set_title("Average Citations per Paper per Year")
    show_fig_with_download(fig, "avg_citations_per_paper_per_year.pdf")

    avg_table = avg_citations_per_year.reset_index()
    avg_table.columns = ["Publication Year", "Average Citations per Paper"]
    st.dataframe(avg_table)
    _download_button(avg_table, "Download CSV", "avg_citations_per_paper.csv")

@safe_run
def display_citation_data_per_year(df: pd.DataFrame):
    st.subheader("Publications vs Citations per Year")

    if "Publication year" not in df.columns:
        st.warning("No 'Publication year' column found.")
        return

    df_year = df.dropna(subset=["Publication year"]).copy()
    df_year["Publication year"] = df_year["Publication year"].astype(int)

    if df_year.empty:
        st.info("No valid publication-year data.")
        return

    # ------------------------------------------------------------------ counts
    pubs_per_year      = df_year.groupby("Publication year").size()
    citations_per_year = df_year.groupby("Publication year")["Times Cited"].sum()

    # We normally ignore the very early years (<1962)
    pubs_per_year      = pubs_per_year[pubs_per_year.index      >= 1962]
    citations_per_year = citations_per_year[citations_per_year.index >= 1962]

    # ------------------------------------------------------------------ plot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(pubs_per_year.index,      pubs_per_year.values,      marker="o",
            label="Publications")
    ax.plot(citations_per_year.index, citations_per_year.values, marker="s",
            label="Citations")

    ax.set_xlabel("Year")
    ax.set_ylabel("Count")
    ax.set_title("Publications and Citations per Year")
    ax.legend()
    show_fig_with_download(fig, "pubs_vs_citations_per_year.pdf")

    # ------------------------------------------------------------------ TABLE
    combined = (
        pd.DataFrame({
            "Publication Year": pubs_per_year.index
        })
        .assign(
            Publications = pubs_per_year.values,
            Citations    = pubs_per_year.index.map(citations_per_year).fillna(0).astype(int)
        )
    )

    st.markdown("### Publications & Citations – side-by-side")
    st.dataframe(combined)

    _download_button(
        combined,
        "Download CSV",
        "publications_vs_citations_per_year.csv"
    )


@safe_run
def display_error_info(df: pd.DataFrame):
    st.header("Error information")

    st.subheader("Articles Missing Citation Information")
    missing_citations = df[df["Times Cited"].isna()][["Title", "Publication year"]]

    total_articles = len(df)
    count_missing = len(missing_citations)
    perc = (count_missing / total_articles * 100) if total_articles else 0.0

    st.markdown(
        f"**{count_missing} articles** are missing citation information "
        f"({perc:.2f}% of {total_articles})."
    )

    if not missing_citations.empty:
        st.dataframe(missing_citations)
        _download_button(
            missing_citations,
            "Download Missing Citations",
            "missing_citations.csv",
        )

        st.subheader("Table of Missing Citation Information by Year")
        year_counts = (
            missing_citations.assign(
                **{
                    "Publication year": missing_citations["Publication year"].fillna(
                        "Unknown"
                    )
                }
            )
            .groupby("Publication year")
            .size()
            .sort_values(ascending=False)
        )

        year_table = year_counts.reset_index(name="Count")
        year_table["Percentage"] = (year_table["Count"] / count_missing * 100).round(2)
        st.dataframe(year_table)
        _download_button(
            year_table, "Download Missing-by-Year", "missing_citations_by_year.csv"
        )

    st.subheader("📊 Articles with Zero or Missing Citations per Year")

    uncited_or_missing = (
        df[df["Times Cited"].isna() | (df["Times Cited"] == 0)]
        .groupby("Publication year")
        .size()
        .reset_index(name="Uncited or Missing")
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        uncited_or_missing["Publication year"].astype(str),
        uncited_or_missing["Uncited or Missing"],
        alpha=0.8,
    )

    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f"{int(height)}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Number of Articles")
    ax.set_title("Articles with Zero or Missing Citations per Year")
    ax.set_xticks(range(len(uncited_or_missing)))
    ax.set_xticklabels(uncited_or_missing["Publication year"].astype(str), rotation=90)
    show_fig_with_download(fig, "uncited_or_missing_per_year.pdf")