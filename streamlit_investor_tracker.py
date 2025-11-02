import streamlit as st
import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, PendingRollbackError

# Layout
st.set_page_config(page_title="Investors Tracker", layout="wide", initial_sidebar_state="expanded")

# --- HIDE STREAMLIT TOP BAR & FOOTER ---
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


# ---------------------- DATABASE CONNECTION ----------------------

@st.cache_resource
def get_engine():
    return create_engine(
        "postgresql+psycopg2://siftedintelligence:PURESHARPIE32$works@"
        "sifted-intelligence-aurora-cluster-prod.cluster-crimj3suf8la.eu-west-1.rds.amazonaws.com/"
        "sifted_intelligence_db"
    )


def safe_read_sql(query, engine):
    """Safely read SQL with rollback and auto-reconnect."""
    try:
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except PendingRollbackError:
        # Reset bad connection and retry once
        engine.dispose()
        engine = get_engine()
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except SQLAlchemyError as e:
        # Ensure rollback if something goes wrong
        try:
            conn.rollback()
        except Exception:
            pass
        st.error(f"Database error: {e}")
        return pd.DataFrame()


# ---------------------- FILTER LOGIC ----------------------

def get_filter_options(_engine):
    def flatten_and_deduplicate(column, table):
        df = safe_read_sql(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL", _engine)
        if df.empty:
            return []
        split_values = df[column].dropna().astype(str).str.split(',').explode().str.strip()
        return sorted({v for v in split_values.dropna().unique().tolist() if v.strip()})

    countries = flatten_and_deduplicate("hq_country", "intelligence.deals")
    cities = flatten_and_deduplicate("hq_city", "intelligence.deals")
    verticals = flatten_and_deduplicate("vertical", "intelligence.deals")
    sectors = flatten_and_deduplicate("sector", "intelligence.deals")
    stages = flatten_and_deduplicate("stage", "intelligence.deals")

    hqs_df = safe_read_sql(
        "SELECT hq_country FROM intelligence.investors WHERE hq_country IS NOT NULL", _engine
    )
    hqs = sorted({v for v in hqs_df.hq_country.dropna().unique().tolist()}) if not hqs_df.empty else []

    df_types = safe_read_sql(
        """
        SELECT i.investor_type
        FROM intelligence.companyinvestors ci
        JOIN intelligence.investors i ON ci.investor_id = i.investor_id
        JOIN intelligence.deals d ON ci.deal_id = d.deal_id
        WHERE i.is_current = TRUE AND ci.acquiror_id IS NULL AND i.investor_type IS NOT NULL
        """, _engine
    )
    split_values = df_types["investor_type"].dropna().astype(str).str.split(',').explode().str.strip() if not df_types.empty else []
    investor_types = sorted({v for v in split_values if v.strip()})

    df_names = safe_read_sql(
        """
        SELECT i.name
        FROM intelligence.companyinvestors ci
        JOIN intelligence.investors i ON ci.investor_id = i.investor_id
        JOIN intelligence.deals d ON ci.deal_id = d.deal_id
        WHERE i.is_current = TRUE AND ci.acquiror_id IS NULL AND i.name IS NOT NULL
        """, _engine
    )
    investor_names = sorted({v for v in df_names.name.dropna().unique().tolist()}) if not df_names.empty else []

    return countries, cities, verticals, sectors, stages, hqs, investor_types, investor_names

def clause(field, values, include=True, ilike=False):
    logic = "IN" if include else "NOT IN"
    if ilike:
        exprs = [f"{field} ILIKE '%%{v}%%'" for v in values]
        return f"({' OR '.join(exprs)})" if include else f"NOT ({' OR '.join(exprs)})"
    else:
        value_list = ", ".join([f"'{v}'" for v in values])
        return f"{field} {logic} ({value_list})"

def round_type_clause(types, include=True):
    clauses = []
    if "Equity" in types:
        clauses.append("(NOT d.round IN ('Grant','Debt','Convertible','Lending capital') OR d.round IS NULL)")
    if "Debt" in types:
        clauses.append("(d.round IN ('Debt','Convertible','Lending capital'))")
    if "Grant" in types:
        clauses.append("(d.round = 'Grant')")
    if not clauses:
        return ""
    expr = ' OR '.join(clauses)
    return f"({expr})" if include else f"(NOT ({expr}))"

def build_query(countries, cities, verticals, sectors, stages, hqs, inv_types,
                start_date, end_date, round_types, exclude_map):
    filters = []
    if countries:
        filters.append(clause("d.hq_country", countries, include=not exclude_map["countries"]))
    if cities:
        filters.append(clause("d.hq_city", cities, include=not exclude_map["cities"]))
    if verticals:
        filters.append(clause("d.vertical", verticals, include=not exclude_map["verticals"], ilike=True))
    if sectors:
        filters.append(clause("d.sector", sectors, include=not exclude_map["sectors"], ilike=True))
    if stages:
        filters.append(clause("d.stage", stages, include=not exclude_map["stages"], ilike=True))
    if hqs:
        filters.append(clause("i.hq_country", hqs, include=not exclude_map["hqs"]))
    if inv_types:
        filters.append(clause("i.investor_type", inv_types, include=not exclude_map["inv_types"], ilike=True))
    if start_date:
        filters.append(f"d.date_announced >= '{start_date.strftime('%Y-%m-%d')}'")
    if end_date:
        filters.append(f"d.date_announced <= '{end_date.strftime('%Y-%m-%d')}'")
    if round_types:
        filters.append(round_type_clause(round_types, include=not exclude_map["round_types"]))

    where_clause = " AND ".join(f"({f})" if ' OR ' in f else f for f in filters) if filters else "TRUE"

    return f"""WITH investor_deals AS (
        SELECT
            i.investor_id, i.name AS investor_name, i.website AS investor_url,
            i.hq_country AS investor_hq, i.investor_type, ci.investor_role,
            d.deal_size_eur, d.hq_country, d.hq_city, d.vertical, d.stage, d.sector
        FROM intelligence.companyinvestors ci
        JOIN intelligence.investors i ON ci.investor_id = i.investor_id
        JOIN intelligence.deals d ON ci.deal_id = d.deal_id
        WHERE i.is_current = TRUE AND ci.acquiror_id is null
          AND {where_clause}
    ),
    agg_base AS (
        SELECT investor_id, investor_name, investor_url, investor_hq, investor_type,
            COUNT(*) FILTER (WHERE investor_role = 'Lead') AS dealcount_lead,
            COUNT(*) FILTER (WHERE investor_role = 'Other') AS dealcount_participating,
            COUNT(*) AS dealcount_all,
            ROUND(AVG(deal_size_eur)) AS average_deal_size,
            ARRAY_AGG(DISTINCT hq_country) AS active_countries,
            ARRAY_AGG(DISTINCT hq_city) AS active_cities,
            ARRAY_AGG(DISTINCT vertical) AS active_verticals,
            ARRAY_AGG(DISTINCT stage) AS active_stages,
            ARRAY_AGG(DISTINCT sector) AS active_sectors
        FROM investor_deals
        GROUP BY investor_id, investor_name, investor_url, investor_hq, investor_type
    ),
    most_active_country AS (
        SELECT investor_id, STRING_AGG(hq_country, ', ') AS most_active_country FROM (
            SELECT investor_id, hq_country, COUNT(*) AS cnt,
                RANK() OVER (PARTITION BY investor_id ORDER BY COUNT(*) DESC) AS rnk
            FROM investor_deals GROUP BY investor_id, hq_country
        ) t WHERE rnk = 1 GROUP BY investor_id
    ),
    most_active_city AS (
        SELECT investor_id, STRING_AGG(hq_city, ', ') AS most_active_city FROM (
            SELECT investor_id, hq_city, COUNT(*) AS cnt,
                RANK() OVER (PARTITION BY investor_id ORDER BY COUNT(*) DESC) AS rnk
            FROM investor_deals GROUP BY investor_id, hq_city
        ) t WHERE rnk = 1 GROUP BY investor_id
    ),
    most_active_vertical AS (
        SELECT investor_id, STRING_AGG(vertical, ', ') AS most_active_vertical FROM (
            SELECT investor_id, vertical, COUNT(*) AS cnt,
                RANK() OVER (PARTITION BY investor_id ORDER BY COUNT(*) DESC) AS rnk
            FROM investor_deals GROUP BY investor_id, vertical
        ) t WHERE rnk = 1 GROUP BY investor_id
    ),
    most_active_stage AS (
        SELECT investor_id, STRING_AGG(stage, ', ') AS most_active_stage FROM (
            SELECT investor_id, stage, COUNT(*) AS cnt,
                RANK() OVER (PARTITION BY investor_id ORDER BY COUNT(*) DESC) AS rnk
            FROM investor_deals GROUP BY investor_id, stage
        ) t WHERE rnk = 1 GROUP BY investor_id
    ),
    most_active_sector AS (
        SELECT investor_id, STRING_AGG(sector, ', ') AS most_active_sector FROM (
            SELECT investor_id, sector, COUNT(*) AS cnt,
                RANK() OVER (PARTITION BY investor_id ORDER BY COUNT(*) DESC) AS rnk
            FROM investor_deals GROUP BY investor_id, sector
        ) t WHERE rnk = 1 GROUP BY investor_id
    )
    SELECT a.*, mac.most_active_country, mcity.most_active_city, mav.most_active_vertical,
           mas.most_active_stage, mase.most_active_sector
    FROM agg_base a
    LEFT JOIN most_active_country mac ON a.investor_id = mac.investor_id
    LEFT JOIN most_active_city mcity ON a.investor_id = mcity.investor_id
    LEFT JOIN most_active_vertical mav ON a.investor_id = mav.investor_id
    LEFT JOIN most_active_stage mas ON a.investor_id = mas.investor_id
    LEFT JOIN most_active_sector mase ON a.investor_id = mase.investor_id
    ORDER BY dealcount_all DESC
    """

def toggle_filter(label, options):
    col1, col2 = st.columns([1, 5])
    with col1:
        is_excluded = st.session_state.get(f"{label}_toggle", False)
        status = "Exclude" if is_excluded else "Include"
        color = "red" if is_excluded else "green"
        st.markdown(f"<div style='text-align:left;color:{color};font-size:12px;'>{status}</div>", unsafe_allow_html=True)
        exclude = st.toggle("", key=f"{label}_toggle")
    with col2:
        values = st.multiselect(label, options, key=label)
    return values, exclude

# Load filter options
engine = get_engine()
countries, cities, verticals, sectors, stages, hqs, investor_types, investor_names = get_filter_options(engine)

# --- Filters UI (arranged per requirements) ---
with st.container():
    # First row: Country, City, Vertical
    c1, _, c2, _, c3 = st.columns([1, 0.2, 1, 0.2, 1])
    with c1:
        countries_f, excl_countries = toggle_filter("🌍 Country", countries)
    with c2:
        cities_f, excl_cities = toggle_filter("🏙️ City", cities)
    with c3:
        verticals_f, excl_verticals = toggle_filter("📦 Vertical", verticals)

    # Second row: Sector, Stage, Round Type
    r1c1, _, r1c2, _, r1c3 = st.columns([1, 0.2, 1, 0.2, 1])
    with r1c1:
        sectors_f, excl_sectors = toggle_filter("🏷️ Sector", sectors)
    with r1c2:
        stages_f, excl_stages = toggle_filter("🚀 Stage", stages)
    with r1c3:
        round_types, excl_rounds = toggle_filter("🌀 Round Type", ["Equity", "Debt", "Grant"])

    # Third row: Date Announced, Investor HQ, Investor Type
    r2c1, _, r2c2, _, r2c3 = st.columns([1, 0.2, 1, 0.2, 1])
    with r2c1:
        date_range = st.date_input("📅 Date Announced", [])
    with r2c2:
        hqs_f, excl_hqs = toggle_filter("📌 Investor HQ", hqs)
    with r2c3:
        types_f, excl_types = toggle_filter("🏢 Investor Type", investor_types)

# Investor name filter (unchanged)
selected_names = st.multiselect("🔍 Search Investor Name", investor_names)

# Parse dates
start_date = end_date = None
if isinstance(date_range, (list, tuple)):
    if len(date_range) == 2:
        start_date, end_date = date_range
    elif len(date_range) == 1:
        start_date = end_date = date_range[0]
elif isinstance(date_range, datetime.date):
    start_date = end_date = date_range

# Loader and data loading
with st.spinner("Loading investors data..."):
    query = build_query(
        countries_f, cities_f, verticals_f, sectors_f, stages_f,
        hqs_f, types_f, start_date, end_date, round_types,
        {
            "countries": excl_countries,
            "cities": excl_cities,
            "verticals": excl_verticals,
            "sectors": excl_sectors,
            "stages": excl_stages,
            "hqs": excl_hqs,
            "inv_types": excl_types,
            "round_types": excl_rounds
        }
    )
    df = pd.read_sql(text(query), engine)

    if selected_names:
        df = df[df["investor_name"].isin(selected_names)]

    df.drop(columns=["investor_id"], errors="ignore", inplace=True)

    def clean_list(x):
        if isinstance(x, (list, tuple)):
            items = []
            for val in x:
                items.extend([v.strip() for v in str(val).split(',') if v.strip()])
            return sorted(set(items))
        else:
            return sorted(set([v.strip() for v in str(x).split(',') if v.strip()]))

    list_cols = [
        "investor_type", "active_countries", "active_cities", "active_verticals", "active_stages", "active_sectors",
        "most_active_country", "most_active_city", "most_active_vertical", "most_active_stage", "most_active_sector"
    ]
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_list)

    if "average_deal_size" in df.columns:
        def fmt(x):
            if pd.isnull(x): return "N/A"
            x = int(round(x))
            if x >= 1_000_000: return f"€{x/1_000_000:.1f}m"
            if x >= 1_000: return f"€{x/1_000:.1f}k"
            return f"€{x}"
        df["average_deal_size"] = df["average_deal_size"].apply(fmt)

    df.rename(columns={
        "investor_name": "Investor Name", "investor_url": "Investor URL",
        "investor_hq": "Investor HQ", "investor_type": "Investor Type",
        "dealcount_lead": "Deal Count (Lead)", "dealcount_participating": "Deal Count (Participating)",
        "dealcount_all": "Deal Count (All)", "average_deal_size": "Average Deal Size",
        "active_countries": "Active Country(s)", "active_cities": "Active City(s)",
        "active_verticals": "Active Vertical(s)", "active_stages": "Active Stage(s)", "active_sectors": "Active Sector(s)",
        "most_active_country": "Most Active Country", "most_active_city": "Most Active City",
        "most_active_vertical": "Most Active Vertical", "most_active_stage": "Most Active Stage", "most_active_sector": "Most Active Sector"
    }, inplace=True)

    desired_order = [
        "Investor Name", "Investor URL", "Investor HQ", "Investor Type",
        "Deal Count (Lead)", "Deal Count (Participating)", "Deal Count (All)", "Average Deal Size",
        "Active Country(s)", "Active City(s)", "Active Vertical(s)", "Active Stage(s)", "Active Sector(s)",
        "Most Active Country", "Most Active City", "Most Active Vertical", "Most Active Stage", "Most Active Sector"
    ]
    df = df[[col for col in desired_order if col in df.columns]]

    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df.index.name = ""

# Make URL clickable
st.dataframe(
    df,use_container_width=True,height=600,
    column_config={'Investor URL': st.column_config.LinkColumn('Investor URL')}
)

st.caption(f"Showing {len(df)} investors matching filters.")

download_cols = [
    "Investor Type", "Active Country(s)", "Active City(s)", "Active Vertical(s)", "Active Stage(s)", "Active Sector(s)",
    "Most Active Country", "Most Active City", "Most Active Vertical", "Most Active Stage", "Most Active Sector"
]
for col in download_cols:
    if col in df.columns:
        df[col] = df[col].apply(lambda x: ", ".join(x) if isinstance(x, (list, tuple)) else x)

st.download_button(
    label="📥 Download CSV",
    data=df.to_csv(index=False),
    file_name="investor_tracker_results.csv",
    mime="text/csv"
)
