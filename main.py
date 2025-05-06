import streamlit as st
import requests
import pandas as pd
import datetime

# --- Fetch Bitcoin Data ---
def fetch_btc_data(days=200):
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily"
    }
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

    data = response.json()
    if 'prices' not in data:
        raise KeyError("Missing 'prices' in API response.")

    df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
    df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('Date', inplace=True)
    df.drop('timestamp', axis=1, inplace=True)
    df.rename(columns={'price': 'Close'}, inplace=True)
    return df

# --- Indicators ---
def calculate_indicators(df):
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()

    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    short_ema = df['Close'].ewm(span=12, adjust=False).mean()
    long_ema = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = short_ema - long_ema
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df

# --- Signal Logic using Etoro Price ---
def interpret_signals(etoro_price, latest):
    sma50 = latest['SMA_50']
    sma200 = latest['SMA_200']
    rsi = latest['RSI']
    macd = latest['MACD']
    macd_signal = latest['MACD_Signal']

    signal_msg = "Neutral/Wait - Hold cash"
    reason_msg = f"RSI = {rsi:.2f}, MACD = {macd:.4f}, Signal = {macd_signal:.4f}, eToro Price = ${etoro_price:.2f}"

    if rsi < 40 and etoro_price < sma50 and macd > macd_signal:
        signal_msg = "Buy Signal - Invest all"
        reason_msg = (
            f"RSI = {rsi:.2f} (< 40), eToro Price = ${etoro_price:.2f} < SMA50 = ${sma50:.2f}, "
            f"MACD = {macd:.4f} > Signal = {macd_signal:.4f} → Recovery starting"
        )
    elif 40 <= rsi < 50 and etoro_price < sma50 and macd > macd_signal:
        signal_msg = "Building Buy Zone - Invest small"
        reason_msg = (
            f"RSI = {rsi:.2f} (40–50), eToro Price = ${etoro_price:.2f} < SMA50 = ${sma50:.2f}, "
            f"MACD = {macd:.4f} > Signal = {macd_signal:.4f} → Possible early trend reversal"
        )
    elif rsi > 65 or macd < macd_signal:
        signal_msg = "Sell Signal - Sell all"
        if rsi > 65 and macd < macd_signal:
            reason_msg = (
                f"RSI = {rsi:.2f} (> 65) and MACD = {macd:.4f} < Signal = {macd_signal:.4f} → Overbought + weakening momentum"
            )
        elif rsi > 65:
            reason_msg = f"RSI = {rsi:.2f} (> 65) → Overbought – possible reversal"
        else:
            reason_msg = f"MACD = {macd:.4f} < Signal = {macd_signal:.4f} → Bearish crossover"
    
    return reason_msg, signal_msg

# --- Streamlit UI ---
st.set_page_config(page_title="Bitcoin Signal Checker", layout="centered")
st.title("📊 Bitcoin Buy/Sell Signal App")

try:
    df = fetch_btc_data(days=200)
    df = calculate_indicators(df)
    latest = df.iloc[-1]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(f"**Date/Time:** {now}")

    # eToro price input
    etoro_price = st.number_input("🔢 Enter current BTC price from eToro (USD):", min_value=0.0, value=float(f"{latest['Close']:.2f}"))

    # Show indicators
    st.markdown(f"**RSI:** {latest['RSI']:.2f}")
    st.markdown(f"**SMA 50:** ${latest['SMA_50']:.2f}")
    st.markdown(f"**SMA 200:** ${latest['SMA_200']:.2f}")
    st.markdown(f"**MACD:** {latest['MACD']:.4f}")
    st.markdown(f"**MACD Signal:** {latest['MACD_Signal']:.4f}")
    
    st.markdown("---")
    reason, signal = interpret_signals(etoro_price, latest)
    st.subheader(f"📢 {signal}")
    st.markdown(f"**Reason:** {reason}")

except Exception as e:
    st.error(f"Something went wrong: {e}")
