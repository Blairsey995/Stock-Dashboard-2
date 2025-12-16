import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="My Stock Tracker", layout="wide")
st.title("📈 My Stock Portfolio Tracker")

st.write("Add your stocks below. Click **Refresh Prices** for live data. Click **Save** to save to Google Sheets (persistent across devices).")

# Google Sheets using Streamlit secrets + sheet ID
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
sheet = client.open_by_key("1Nr1f3sV7-sz5eaPtNek84sRaMFnKFI9JWK9GSHpz1F4").sheet1  # Your sheet ID

def load_holdings():
    try:
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0.0)
            df["Buy Price ($)"] = pd.to_numeric(df["Buy Price ($)"], errors="coerce").fillna(0.0)
            df["Your Target Price ($)"] = pd.to_numeric(df["Your Target Price ($)"], errors="coerce").fillna(0.0)
            return df
        else:
            return pd.DataFrame(columns=["Ticker", "Shares", "Buy Price ($)", "Your Target Price ($)"])
    except Exception as e:
        st.warning(f"Google Sheets load failed: {e}. Starting with empty table.")
        return pd.DataFrame(columns=["Ticker", "Shares", "Buy Price ($)", "Your Target Price ($)"])

def save_holdings(df):
    try:
        sheet.clear()
        sheet.append_row(df.columns.tolist())
        sheet.append_rows(df.values.tolist())
        st.success("Holdings saved to Google Sheets!")
    except Exception as e:
        st.error(f"Save failed: {e}")

if 'holdings' not in st.session_state:
    st.session_state.holdings = load_holdings()

edited = st.data_editor(
    st.session_state.holdings,
    num_rows="dynamic",
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", required=True),
        "Shares": st.column_config.NumberColumn("Shares", min_value=0.01, format="%.4f"),
        "Buy Price ($)": st.column_config.NumberColumn("Buy Price ($)", min_value=0.01, format="$%.2f"),
        "Your Target Price ($)": st.column_config.NumberColumn("Your Target ($)", min_value=0.01, format="$%.2f"),
    },
    hide_index=True
)

st.session_state.holdings = edited

if st.button("💾 Save to Google Sheets", type="secondary", use_container_width=True):
    save_holdings(edited)

if st.button("🔄 Refresh Prices", type="primary", use_container_width=True):
    with st.spinner("Fetching live prices and analyst targets..."):
        current_prices = []
        current_values = []
        total_costs = []
        profits_dollar = []
        profits_pct = []
        analyst_targets = []
        analyst_upside = []

        for _, row in edited.iterrows():
            ticker = str(row["Ticker"]).strip().upper() if pd.notna(row["Ticker"]) else ""
            shares = float(row["Shares"]) if pd.notna(row["Shares"]) else 0.0
            buy_price = float(row["Buy Price ($)"]) if pd.notna(row["Buy Price ($)"]) else 0.0
            your_target = float(row["Your Target Price ($)"]) if pd.notna(row["Your Target Price ($)"]) else None

            price = None
            analyst = None
            if ticker:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    price = info.get("currentPrice") or info.get("regularMarketPrice")
                    price = round(price, 2) if price else None
                    analyst = info.get("targetMeanPrice")
                    analyst = round(analyst, 2) if analyst else None
                except Exception as e:
                    st.error(f"Error fetching {ticker}: {e}")

            current_prices.append(price)
            value = round(price * shares, 2) if price and shares else None
            current_values.append(value)
            cost = round(buy_price * shares, 2) if buy_price and shares else None
            total_costs.append(cost)
            profit_dollar = round(value - cost, 2) if value is not None and cost is not None else None
            profits_dollar.append(profit_dollar)
            profit_pct = round((profit_dollar / cost) * 100, 2) if profit_dollar is not None and cost and cost != 0 else None
            profits_pct.append(profit_pct)
            analyst_targets.append(analyst)
            upside = round(((analyst - price) / price) * 100, 2) if analyst and price and price > 0 else None
            analyst_upside.append(upside)

        edited["Current Price"] = current_prices
        edited["Current Value ($)"] = current_values
        edited["Total Cost ($)"] = total_costs
        edited["Profit/Loss ($)"] = profits_dollar
        edited["Profit/Loss (%)"] = profits_pct
        edited["Analyst Target"] = analyst_targets
        edited["Analyst Upside (%)"] = analyst_upside

    total_value = sum(v for v in current_values if v)
    total_cost = sum(c for c in total_costs if c)
    total_profit = sum(p for p in profits_dollar if p is not None)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Portfolio Value", f"${total_value:,.2f}")
    col2.metric("Total Invested", f"${total_cost:,.2f}")
    col3.metric("Total Profit/Loss", f"${total_profit:+,.2f}", delta=f"{(total_profit/total_cost)*100 if total_cost and total_cost != 0 else 0:+.2f}%")

    st.dataframe(
        edited,
        use_container_width=True
    )

    if not edited.empty:
        chart_df = edited.dropna(subset=["Current Price", "Your Target Price ($)", "Analyst Target"], how="all")
        if not chart_df.empty:
            st.subheader("Price Comparison")
            chart_data = chart_df.set_index("Ticker")[["Current Price", "Your Target Price ($)", "Analyst Target"]]
            chart_data = chart_data.rename(columns={"Your Target Price ($)": "Your Target"})
            st.bar_chart(chart_data)

        value_df = edited.dropna(subset=["Current Value ($)"])
        if not value_df.empty:
            st.subheader("Portfolio Allocation")
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(value_df["Current Value ($)"], labels=value_df["Ticker"], autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
            st.pyplot(fig)

st.info("Your holdings are loaded from and saved to Google Sheets — persistent across devices!")

