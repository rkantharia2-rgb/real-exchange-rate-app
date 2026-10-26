# Real Exchange Rate Explorer

An interactive Streamlit app using monthly IMF CPI and exchange-rate data. Select Country 1 and Country 2 (including the euro area), select a sample, compare nominal exchange rates with an inflation-adjusted real exchange-rate index, and export all calculations as CSV.

## Data

The app requests monthly data from the IMF SDMX 3.0 API (`https://api.imf.org/external/sdmx/3.0`). CPI is queried using `IMF.STA/CPI`, indicator `CPI`, unit `IX`, frequency `M`. Exchange rates are queried from `IMF.STA/IFS`, indicator `XDC_USD_PA_RT`, frequency `M`. Data start in January 1976 where available; country coverage and API availability vary. No fabricated data or API key is used.

## Calculations

- `S(t)`: Country 2 currency units per one Country 1 currency unit.
- `P1(t)` and `P2(t)`: monthly CPI indexes.
- `RER(t) = S(t) × P1(t) / P2(t)`.
- `RER*`: arithmetic mean of RER over valid months in the selected date range.
- `Real Index(t) = 100 × RER(t) / RER*` (average exactly 100, aside from rounding).

The IMF exchange-rate indicator is local-currency units per USD. The app first converts it to USD per local currency, then computes the cross rate. USD itself is 1 USD per USD. The nominal exchange rate is never normalized.

## Deploy

1. Put `app.py`, `requirements.txt`, and `README.md` in the repository root.
2. Sign into https://share.streamlit.io with GitHub and choose **Create app → Yup, I have an app**.
3. Select this repository, branch `main`, and main file `app.py`.
4. In Advanced settings, choose Python 3.12; leave Secrets empty.
5. Deploy. Choose UK as Country 1 and U.S. as Country 2, change the sample dates, and download the CSV.

## Verification

For any exported row, verify `RER = S × CPI_1 / CPI_2`. Verify the CSV's Real Index column averages 100 (subject to rounding). Changing start/end dates should change `RER*` and recompute the Real Index. The exported file includes all valid monthly observations and intermediate calculations.

## Limitations

IMF datasets, indicator keys, and live service responses can change. A missing series or IMF outage will produce an error instead of silently using an alternative source. Some countries have shorter histories or gaps. The euro area uses IMF code G163 and is available only when the relevant IMF series exist.
