import datetime
import json

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

# ----------------------------------------------------------------------
# 📈 Stock Explorer
# Search any company, compare growth over decades (live data from Yahoo
# Finance via yfinance), and see what an investment would be worth today.
# ----------------------------------------------------------------------

st.set_page_config(page_title="Stock Explorer", page_icon="📈", layout="wide")

# Brand colors so each well-known company shows in its own color.
BRAND_COLORS = {
    "AAPL": "#9DA3A8",  # Apple silver-grey
    "MSFT": "#00A4EF",  # Microsoft blue
    "GOOG": "#4285F4",
    "GOOGL": "#4285F4",  # Google blue
    "AMZN": "#FF9900",  # Amazon orange
    "META": "#0866FF",
    "FB": "#0866FF",  # Meta blue
    "NFLX": "#E50914",  # Netflix red
    "NVDA": "#76B900",  # Nvidia green
    "TSLA": "#E82127",  # Tesla red
    "AMD": "#ED1C24",
    "INTC": "#0071C5",
    "IBM": "#1F70C1",
    "DIS": "#1A6DFF",
    "KO": "#F40009",  # Coca-Cola red
    "PEP": "#28458E",
    "SPOT": "#1DB954",  # Spotify green
    "ORCL": "#F80000",
    "CRM": "#00A1E0",
    "UBER": "#000000",
}
ACCENT = "#8B7CF6"
DEFAULTS = ["AAPL", "MSFT", "GOOGL", "NVDA"]

# Real facts gathered with the Fetch skill pack (rotate client-side every 15s).
FACTS = [
    "In 2000, Blockbuster turned down the chance to buy Netflix for just <b>$50 million</b>.",
    "In 1997, a nearly-bankrupt Apple was rescued when <b>Microsoft invested $150 million</b> in it.",
    "After returning to Apple in 1997, Steve Jobs paid himself a salary of <b>$1 a year</b>.",
    "Nvidia was founded in 1993 over a meal at a <b>Denny's</b> near San Jose, with $40,000 in seed money.",
    "Microsoft put Windows on smartphones in 2000 — <b>seven years before</b> the first iPhone.",
    "Amazon began in 1994 as an online bookstore run out of Jeff Bezos's <b>garage</b> in Seattle.",
    "Netflix was founded in 1997, making it <b>a year older than Google</b>.",
    "Microsoft is one of the world's largest corporate art collectors, with <b>5,000+ pieces</b>.",
]


# ---------------------------- Data helpers ----------------------------
@st.cache_data(ttl=900, show_spinner=False)
def search_symbols(query):
    """Resolve a company name or ticker to candidate symbols via Yahoo Finance."""
    query = (query or "").strip()
    if not query:
        return []
    # Preferred: yfinance's built-in search.
    try:
        import yfinance as yf

        out = []
        for q in yf.Search(query, max_results=8).quotes:
            sym = q.get("symbol")
            name = q.get("shortname") or q.get("longname") or ""
            if sym:
                out.append((sym, name))
        if out:
            return out
    except Exception:
        pass
    # Fallback: Yahoo Finance search endpoint.
    try:
        import requests

        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 8, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        return [
            (q.get("symbol"), q.get("shortname", ""))
            for q in r.json().get("quotes", [])
            if q.get("symbol")
        ]
    except Exception:
        return []


@st.cache_data(ttl=900, show_spinner=False)
def fetch_prices(tickers, start, end):
    """Download adjusted close prices for the given tickers from Yahoo Finance."""
    import yfinance as yf

    tickers = list(tickers)
    if not tickers:
        return pd.DataFrame()
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:  # single ticker -> flat columns
        close = raw[["Close"]].copy()
        close.columns = tickers[:1]
    close = close.dropna(how="all")
    close.index.name = "Date"
    return close


def dark_chart(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10),
    )
    return fig


# ------------------------------- Header -------------------------------
st.title("📈 Stock Explorer")
st.caption(
    "Search any company, compare growth over decades, and see what an investment "
    "would be worth today. Prices are indexed to 1.00 at the start of your window, "
    "so every line shows growth from there. Live data from Yahoo Finance."
)

# Auto-rotating fun fact — pure client-side, refreshes every 15s, no page reload.
components.html(
    f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#23232F;
                border-left:4px solid {ACCENT};padding:12px 16px;border-radius:10px;
                color:#E8E8EC;font-size:15px;line-height:1.4;">
      <span style="opacity:.65;">💡 Did you know?</span>
      <span id="fact" style="transition:opacity .4s ease;opacity:1;"></span>
    </div>
    <script>
      const facts = {json.dumps(FACTS)};
      let i = Math.floor(Math.random() * facts.length);
      const el = document.getElementById('fact');
      function show() {{
        el.style.opacity = 0;
        setTimeout(() => {{
          el.innerHTML = ' ' + facts[i];
          el.style.opacity = 1;
          i = (i + 1) % facts.length;
        }}, 400);
      }}
      show();
      setInterval(show, 15000);
    </script>
    """,
    height=72,
)

# ------------------------------- Sidebar ------------------------------
if "portfolio" not in st.session_state:
    st.session_state.portfolio = DEFAULTS.copy()

st.sidebar.header("🔎 Find a stock")
with st.sidebar.form("search_form", clear_on_submit=False):
    query = st.text_input("Company name or ticker", placeholder="e.g. Nvidia, Coca-Cola, TSLA")
    do_search = st.form_submit_button("Search")
if do_search and query:
    st.session_state.results = search_symbols(query)

results = st.session_state.get("results", [])
if results:
    label_map = {(f"{s} — {n}" if n else s): s for s, n in results}
    pick = st.sidebar.selectbox("Search results", list(label_map.keys()))
    if st.sidebar.button("➕ Add to comparison"):
        sym = label_map[pick]
        if sym not in st.session_state.portfolio:
            st.session_state.portfolio.append(sym)
        st.sidebar.success(f"Added {sym}")

st.sidebar.divider()
st.sidebar.header("⚙️ Compare")
chosen = st.sidebar.multiselect(
    "Stocks in your comparison",
    options=sorted(set(st.session_state.portfolio)),
    default=st.session_state.portfolio,
)

today = datetime.date.today()
date_range = st.sidebar.date_input(
    "📅 Date range",
    value=(datetime.date(2000, 1, 1), today),
    min_value=datetime.date(1980, 1, 1),
    max_value=today,
)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = date_range
else:
    start, end = datetime.date(2000, 1, 1), today

# ------------------------------- Body ---------------------------------
if not chosen:
    st.warning("Search for a company in the sidebar and add it, or pick one from the list.")
    st.stop()

with st.spinner("Fetching live prices from Yahoo Finance…"):
    close = fetch_prices(tuple(chosen), start, end)

if close.empty:
    st.error(
        "Couldn't fetch data for those tickers in that range. "
        "Try different tickers or a wider date range."
    )
    st.stop()

available = [c for c in chosen if c in close.columns and close[c].notna().any()]
missing = [c for c in chosen if c not in available]
if missing:
    st.warning("No data found for: " + ", ".join(missing))
if not available:
    st.error("None of the selected tickers returned data for this date range. Try another ticker or a wider range.")
    st.stop()
close = close[available]

# Re-index each stock to 1.00 at the start of the selected window.
norm = close.copy()
for c in norm.columns:
    s = norm[c].dropna()
    if not s.empty:
        norm[c] = norm[c] / s.iloc[0]

growth_pct = {c: (norm[c].dropna().iloc[-1] - 1) * 100 for c in available}

# ---- Key metrics ----
st.subheader("Growth over the selected window")
metric_cols = st.columns(len(available))
for col, c in zip(metric_cols, available):
    col.metric(c, f"{norm[c].dropna().iloc[-1]:.2f}x", f"{growth_pct[c]:+.1f}%")

best = max(growth_pct, key=growth_pct.get)
volatility = {c: close[c].pct_change().std() * 100 for c in available}
most_volatile = max(volatility, key=volatility.get)
h1, h2 = st.columns(2)
h1.metric("🏆 Best performer", best, f"{growth_pct[best]:+.1f}%")
h2.metric("🌪️ Most volatile", most_volatile, f"±{volatility[most_volatile]:.2f}% daily swing")

# ---- What if I invested? ----
st.subheader("💸 What if I had invested?")
i1, i2 = st.columns(2)
invest_stock = i1.selectbox("Stock", available)
amount = i2.number_input("Amount invested ($)", min_value=1, value=1000, step=100)
final_value = amount * norm[invest_stock].dropna().iloc[-1]
profit = final_value - amount
st.markdown(
    f"Investing **${amount:,.0f}** in **{invest_stock}** at the start of this window "
    f"would be worth **${final_value:,.0f}** today (**${profit:+,.0f}**)."
)

# ---- Line chart (brand colors) ----
st.subheader("Normalized price over time")
plot_df = norm.reset_index().melt(
    id_vars="Date", var_name="Stock", value_name="Indexed price"
)
line = px.line(
    plot_df, x="Date", y="Indexed price", color="Stock", color_discrete_map=BRAND_COLORS
)
line.update_layout(legend_title_text="Stock", hovermode="x unified")
st.plotly_chart(dark_chart(line), use_container_width=True)

# ---- Bar chart of total growth ----
st.subheader("Total growth by stock")
bar_df = pd.DataFrame({"Stock": list(growth_pct), "Growth %": list(growth_pct.values())})
bar = px.bar(
    bar_df, x="Stock", y="Growth %", color="Stock",
    color_discrete_map=BRAND_COLORS, text="Growth %",
)
bar.update_traces(texttemplate="%{text:+.1f}%", textposition="outside")
bar.update_layout(showlegend=False)
st.plotly_chart(dark_chart(bar), use_container_width=True)

st.caption(
    "Live data: Yahoo Finance via yfinance (adjusted close). "
    "Built by Adam · driven through Claude + MCP skill packs."
)
