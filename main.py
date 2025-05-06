import streamlit as st
import requests
import pandas as pd
import datetime

# --- Fetch BTC data from CoinGecko ---
import streamlit as st
import time

@st.cache_data(ttl=300)  # cache for 5 minutes
def fetch_btc_data(days=200):
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code}")
    data = response.json()
    if 'prices' not in data:
        raise KeyError("Missing 'prices' in API response")
    df = pd.DataFrame(data['prices'], columns=["timestamp", "Close"])
    df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("Date", inplace=True)
    df.drop("timestamp", axis=1, inplace=True)
    return df


# --- Technical Indicators ---
def calculate_indicators(df):
    df["SMA_50"] = df["Close"].rolling(window=50).mean()
    df["SMA_200"] = df["Close"].rolling(window=200).mean()

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    short_ema = df["Close"].ewm(span=12, adjust=False).mean()
    long_ema = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = short_ema - long_ema
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    return df

# --- Signal Logic ---
def get_signal(latest, override_price=None):
    rsi = latest["RSI"]
    price = override_price if override_price else latest["Close"]
    sma50 = latest["SMA_50"]
    sma200 = latest["SMA_200"]
    macd = latest["MACD"]
    macd_signal = latest["MACD_Signal"]

    price_used = "Broker Price" if override_price else "Market Price"

    if rsi > 65 or macd < macd_signal:
        if rsi > 65 and macd < macd_signal:
            reason = f"RSI = {rsi:.2f} (>65) and MACD = {macd:.4f} < Signal = {macd_signal:.4f} → Overbought + bearish momentum"
        elif rsi > 65:
            reason = f"RSI = {rsi:.2f} (>65) → Overbought"
        else:
            reason = f"MACD = {macd:.4f} < Signal = {macd_signal:.4f} → Bearish crossover"
        return "Sell Signal - Sell all", reason, price_used

    elif rsi < 35 and price < sma50 and pd.notna(sma200) and price > sma200 and macd > macd_signal:
        reason = f"RSI = {rsi:.2f} (<35), Price = ${price:.2f} < SMA50 = ${sma50:.2f}, > SMA200 = ${sma200:.2f}, MACD = {macd:.4f} > Signal = {macd_signal:.4f}"
        return "Buy Signal - Invest all", reason, price_used

    elif 35 <= rsi < 45 and price <= sma50 and macd > macd_signal:
        reason = f"RSI = {rsi:.2f} (35–45), Price = ${price:.2f} ≤ SMA50 = ${sma50:.2f}, MACD = {macd:.4f} > Signal = {macd_signal:.4f}"
        return "Building Buy Zone - Invest small", reason, price_used

    return "Neutral/Wait - Hold cash", f"RSI = {rsi:.2f}, MACD = {macd:.4f}, Signal = {macd_signal:.4f} → No strong alignment", price_used

# --- Streamlit UI ---
st.set_page_config(page_title="BTC Signal Checker", layout="centered")
st.title("🧠 Bitcoin Signal Dashboard")

try:
    df = fetch_btc_data()
    df = calculate_indicators(df)
    latest = df.iloc[-1]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    market_price = latest["Close"]
    st.markdown(f"**Date/Time:** {now}")
    st.markdown(f"**CoinGecko Market Price:** ${market_price:.2f}")

    # Optional broker price input
    broker_price_input = st.text_input("Optional: Enter eToro/Broker BTC price (USD)", "")
    try:
        broker_price = float(broker_price_input) if broker_price_input else None
    except ValueError:
        st.warning("Invalid price input. Please enter a number.")
        broker_price = None

    # Warning if price mismatch is large
    if broker_price:
        pct_diff = abs((broker_price - market_price) / market_price) * 100
        st.markdown(f"**Your Broker Price:** ${broker_price:.2f}")
        if pct_diff > 1.5:
            st.error(f"⚠️ Broker price differs by {pct_diff:.2f}% from market. Signal accuracy may be affected.")

    st.markdown("---")
    st.markdown(f"**RSI (14-day):** {latest['RSI']:.2f}")
    st.markdown(f"**SMA 50:** ${latest['SMA_50']:.2f}")
    st.markdown(f"**SMA 200:** ${latest['SMA_200']:.2f}")
    st.markdown(f"**MACD:** {latest['MACD']:.4f}")
    st.markdown(f"**MACD Signal:** {latest['MACD_Signal']:.4f}")

    signal, reason, source = get_signal(latest, override_price=broker_price)
    st.markdown("---")
    st.subheader(f"📢 {signal}")
    st.markdown(f"**Reason:** {reason}")
    st.caption(f"Based on: {source}")

except Exception as e:
    st.error(f"Something went wrong: {e}")
