"""Interactive real exchange rates from IMF SDMX 3.0 monthly data."""
import io
import re
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

API = "https://api.imf.org/external/sdmx/3.0/data/dataflow"
COUNTRIES = {
    "United States": ("USA", "USD"), "United Kingdom": ("GBR", "GBP"),
    "Euro area": ("G163", "EUR"), "Canada": ("CAN", "CAD"),
    "Japan": ("JPN", "JPY"), "Australia": ("AUS", "AUD"),
    "Switzerland": ("CHE", "CHF"), "India": ("IND", "INR"),
    "China": ("CHN", "CNY"), "Mexico": ("MEX", "MXN"),
    "Brazil": ("BRA", "BRL"), "South Korea": ("KOR", "KRW"),
    "South Africa": ("ZAF", "ZAR"), "Sweden": ("SWE", "SEK"),
    "Norway": ("NOR", "NOK"), "Denmark": ("DNK", "DKK"),
    "New Zealand": ("NZL", "NZD"), "Singapore": ("SGP", "SGD"),
    "Turkey": ("TUR", "TRY"), "Indonesia": ("IDN", "IDR"),
    "Thailand": ("THA", "THB"), "Malaysia": ("MYS", "MYR"),
    "Philippines": ("PHL", "PHP"), "Israel": ("ISR", "ILS"),
    "Poland": ("POL", "PLN"), "Czech Republic": ("CZE", "CZK"),
    "Hungary": ("HUN", "HUF"), "Chile": ("CHL", "CLP"),
    "Colombia": ("COL", "COP"), "Peru": ("PER", "PEN"),
    "Argentina": ("ARG", "ARS"), "Saudi Arabia": ("SAU", "SAR"),
    "United Arab Emirates": ("ARE", "AED"), "Egypt": ("EGY", "EGP"),
    "Pakistan": ("PAK", "PKR"), "Bangladesh": ("BGD", "BDT"),
    "Vietnam": ("VNM", "VND"), "Nigeria": ("NGA", "NGN"),
    "Kenya": ("KEN", "KES"), "Morocco": ("MAR", "MAD"),
    "Romania": ("ROU", "RON"), "Bulgaria": ("BGR", "BGN"),
    "Iceland": ("ISL", "ISK"), "Russia": ("RUS", "RUB"),
}

st.set_page_config(page_title="IMF Real Exchange Rate Explorer", layout="wide")
st.title("🌍 IMF Real Exchange Rate Explorer")
st.caption("Monthly IMF data • nominal and inflation-adjusted exchange rates • January 1976 onward where available")

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def imf_csv(flow, key):
    url = f"{API}/{flow}/~/{key}"
    response = requests.get(url, params={"c[TIME_PERIOD]": "ge:1976-M01"},
                            headers={"Accept": "text/csv"}, timeout=55)
    response.raise_for_status()
    if not response.content or response.status_code == 204:
        raise ValueError("The IMF returned no observations.")
    frame = pd.read_csv(io.StringIO(response.text), low_memory=False)
    frame.columns = frame.columns.str.upper().str.strip()
    if "TIME_PERIOD" not in frame or "OBS_VALUE" not in frame:
        raise ValueError("Unexpected IMF data format (missing date or observation).")
    return frame


def monthly_series(frame, country, indicator=None):
    df = frame.copy()
    if "COUNTRY" in df:
        df = df[df["COUNTRY"].astype(str).str.upper() == country]
    if indicator and "INDICATOR" in df:
        df = df[df["INDICATOR"].astype(str).str.upper() == indicator]
    if "FREQUENCY" in df:
        df = df[df["FREQUENCY"].astype(str).str.upper() == "M"]
    if "FREQ" in df:
        df = df[df["FREQ"].astype(str).str.upper() == "M"]
    dates = pd.to_datetime(df["TIME_PERIOD"].astype(str).str.replace(r"-M(?=\d\d$)", "-", regex=True), errors="coerce")
    values = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    s = pd.Series(values.to_numpy(), index=dates).dropna()
    s = s[s.index.notna() & (s > 0)]
    return s[~s.index.duplicated(keep="last")].sort_index()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_cpi(code):
    # IMF CPI dimension order: COUNTRY.INDICATOR.COICOP.UNIT_MEASURE.FREQUENCY
    candidates = [
        ("IMF.STA/CPI", f"{code}.CPI._T.IX.M"),
        ("IMF.STA/CPI", f"{code}.CPI.*.IX.M"),
    ]
    errors = []
    for flow, key in candidates:
        try:
            s = monthly_series(imf_csv(flow, key), code, "CPI")
            if len(s) >= 2:
                return s
        except (requests.RequestException, ValueError, pd.errors.ParserError) as exc:
            errors.append(str(exc))
    raise ValueError(f"No usable monthly CPI observations for {code}. " + "; ".join(errors[:1]))


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_usd_per_local(code):
    if code == "USA":
        return None  # Exactly 1 USD per USD; no IMF series needed.
    # IFS series is quoted in local-currency units per USD. Invert it.
    candidates = [
        ("IMF.STA/IFS", f"{code}.XDC_USD_PA_RT.M"),
        ("IMF.STA/IFS", f"{code}.XDC_USD_PA_RT.*.M"),
    ]
    errors = []
    for flow, key in candidates:
        try:
            s = monthly_series(imf_csv(flow, key), code, "XDC_USD_PA_RT")
            if len(s) >= 2:
                return 1.0 / s
        except (requests.RequestException, ValueError, pd.errors.ParserError) as exc:
            errors.append(str(exc))
    raise ValueError(f"No usable monthly exchange-rate observations for {code}. " + "; ".join(errors[:1]))


names = list(COUNTRIES)
with st.sidebar:
    st.header("Choose your comparison")
    country1 = st.selectbox("Country 1 (base currency)", names, index=names.index("United Kingdom"))
    country2 = st.selectbox("Country 2 (quote currency)", names, index=names.index("United States"))
    chart_choice = st.radio("Show", ["Both", "Nominal", "Real"], horizontal=True)
    st.caption("Dates and calculations will be selected after available data load.")

if country1 == country2:
    st.info("Choose two different countries.")
    st.stop()

code1, curr1 = COUNTRIES[country1]
code2, curr2 = COUNTRIES[country2]

try:
    with st.spinner("Downloading monthly CPI and exchange-rate observations from the IMF…"):
        p1 = fetch_cpi(code1).rename("P1_CPI")
        p2 = fetch_cpi(code2).rename("P2_CPI")
        usd1 = fetch_usd_per_local(code1)
        usd2 = fetch_usd_per_local(code2)
        parts = [p1, p2]
        if usd1 is not None:
            parts.append(usd1.rename("USD_per_currency1"))
        if usd2 is not None:
            parts.append(usd2.rename("USD_per_currency2"))
        all_data = pd.concat(parts, axis=1).sort_index()
        if usd1 is None:
            all_data["USD_per_currency1"] = 1.0
        if usd2 is None:
            all_data["USD_per_currency2"] = 1.0
        all_data["S_nominal"] = all_data["USD_per_currency1"] / all_data["USD_per_currency2"]
        all_data = all_data.dropna(subset=["P1_CPI", "P2_CPI", "S_nominal"])
        all_data = all_data[(all_data[["P1_CPI", "P2_CPI", "S_nominal"]] > 0).all(axis=1)]
        all_data = all_data[all_data.index >= pd.Timestamp("1976-01-01")]
        if all_data.empty:
            raise ValueError("The IMF has no overlapping monthly CPI and exchange-rate observations for this pair.")
except (ValueError, requests.RequestException, KeyError) as exc:
    st.error("Could not load this IMF country pair. IMF coverage and live API availability vary.")
    st.code(str(exc))
    st.info("Try United Kingdom / United States, or retry later. The app does not substitute made-up data.")
    st.stop()

min_date = all_data.index.min().date()
max_date = all_data.index.max().date()
with st.sidebar:
    start = st.date_input("Start month", value=min_date, min_value=min_date, max_value=max_date)
    end = st.date_input("End month", value=max_date, min_value=min_date, max_value=max_date)

if start > end:
    st.warning("The start date must be on or before the end date.")
    st.stop()

sample = all_data.loc[(all_data.index.to_period("M") >= pd.Period(start, freq="M")) &
                      (all_data.index.to_period("M") <= pd.Period(end, freq="M"))].copy()
if sample.empty:
    st.warning("No complete monthly observations exist in that date range. Widen the dates.")
    st.stop()

# The assignment's convention: S = Country 2 currency / Country 1 currency.
sample["RER"] = sample["S_nominal"] * sample["P1_CPI"] / sample["P2_CPI"]
rer_star = sample["RER"].mean()
sample["Real_Index"] = 100 * sample["RER"] / rer_star
sample.index.name = "Month"

st.subheader(f"{country1} → {country2}")
st.write(f"**S(t): {curr2} per 1 {curr1}** (actual currency units, not normalized).")
a, b, c = st.columns(3)
a.metric("Valid months", f"{len(sample):,}")
b.metric("Average real exchange rate (RER*)", f"{rer_star:,.5f}")
c.metric("Average real index", f"{sample['Real_Index'].mean():.2f}")

if chart_choice in ("Nominal", "Both"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sample.index, y=sample["S_nominal"], mode="lines", name="Nominal S(t)"))
    fig.update_layout(title=f"Nominal exchange rate — {curr2} per {curr1}",
                      xaxis_title="Month", yaxis_title=f"{curr2} per {curr1}")
    st.plotly_chart(fig, use_container_width=True)
if chart_choice in ("Real", "Both"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sample.index, y=sample["Real_Index"], mode="lines", name="Real index"))
    fig.add_hline(y=100, line_dash="dash", annotation_text="Sample average = 100")
    fig.update_layout(title="Real exchange rate index (sample average = 100)",
                      xaxis_title="Month", yaxis_title="Real index")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("**Economic formulas**")
st.latex(r"RER_t = S_t \times \frac{P_{1,t}}{P_{2,t}}")
st.latex(r"RER^* = \operatorname{mean}(RER_t), \qquad RealIndex_t = 100 \times \frac{RER_t}{RER^*}")
st.caption("Only months with complete positive observations are included. RER* is recalculated for the selected sample.")

export = sample[["S_nominal", "P1_CPI", "P2_CPI", "RER", "Real_Index"]].reset_index()
export["Month"] = export["Month"].dt.strftime("%Y-%m")
export = export.rename(columns={"S_nominal": f"S_{curr2}_per_{curr1}",
                                "P1_CPI": f"CPI_{code1}", "P2_CPI": f"CPI_{code2}"})
st.download_button("Download complete sample as CSV", export.to_csv(index=False).encode("utf-8"),
                   file_name=f"real_exchange_rate_{code1}_{code2}.csv", mime="text/csv")
with st.expander("View calculations and underlying data"):
    st.dataframe(export, use_container_width=True)
    st.write("Manual check: for any row, multiply S by Country 1 CPI and divide by Country 2 CPI. Then divide that RER by the sample-average RER and multiply by 100.")
    st.write("IMF data: CPI (IMF.STA/CPI) and IFS exchange rates (IMF.STA/IFS), SDMX 3.0 API. Exchange rates quoted as local units per USD are inverted before forming the currency cross rate.")
