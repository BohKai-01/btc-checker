import requests
import pandas as pd
import datetime
import streamlit as st

# --- Fetch BTC Data ---
def fetch_btc_data(days=200):
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

    data = response.json()

    if 'prices' not in data:
        raise KeyError("Key 'prices' not found in API response:\n" + str(data))

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

# --- Interpret Signal ---
def interpret_signals(latest):
    price = latest['Close']
    sma50 = latest['SMA_50']
    sma200 = latest['SMA_200']
    rsi = latest['RSI']
    macd = latest['MACD']
    macd_signal = latest['MACD_Signal']

    signal_msg = "Neutral/Wait - Hold cash"
    reason_msg = (
        f"RSI = {rsi:.2f}, MACD = {macd:.4f}, Signal = {macd_signal:.4f}, "
        f"Price = ${price:.2f}, SMA50 = ${sma50:.2f}, SMA200 = ${sma200:.2f} → No strong alignment"
    )

    if rsi > 65 or macd < macd_signal:
        signal_msg = "Sell Signal - Sell all"
        if rsi > 65 and macd < macd_signal:
            reason_msg = f"RSI = {rsi:.2f} (>65) and MACD = {macd:.4f} < {macd_signal:.4f} → Overbought + bearish momentum"
        elif rsi > 65:
            reason_msg = f"RSI = {rsi:.2f} (>65) → Overbought condition – likely pullback"
        else:
            reason_msg = f"MACD = {macd:.4f} < {macd_signal:.4f} → Bearish crossover"

    elif rsi < 35 and price < sma50 and pd.notna(sma200) and price > sma200 and macd > macd_signal:
        signal_msg = "Buy Signal - Invest all"
        reason_msg = f"RSI = {rsi:.2f} (<35), Price = ${price:.2f} < SMA50 = ${sma50:.2f}, > SMA200 = ${sma200:.2f}, MACD = {macd:.4f} > {macd_signal:.4f}"

    elif 35 <= rsi < 45 and price <= sma50 and macd > macd_signal:
        signal_msg = "Building Buy Zone - Invest some"
        reason_msg = f"RSI = {rsi:.2f} (35–45), Price = ${price:.2f} ≤ SMA50 = ${sma50:.2f}, MACD = {macd:.4f} > {macd_signal:.4f}"

    return signal_msg, reason_msg

# --- Streamlit UI ---
st.set_page_config(page_title="BTC Signal Checker", layout="centered")
st.title("📈 Bitcoin Trading Signal")

try:
    df = fetch_btc_data()
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    st.markdown(f"**Date/Time:** {now}")
    st.markdown(f"**BTC Price:** ${latest['Close']:.2f}")
    st.markdown(f"**RSI (14-day):** {latest['RSI']:.2f}")
    st.markdown(f"**SMA 50:** ${latest['SMA_50']:.2f}")
    st.markdown(f"**SMA 200:** ${latest['SMA_200']:.2f}")
    st.markdown(f"**MACD:** {latest['MACD']:.4f}")
    st.markdown(f"**MACD Signal:** {latest['MACD_Signal']:.4f}")
    
    st.markdown("---")
    signal, reason = interpret_signals(latest)
    st.subheader(signal)
    st.markdown(f"**Reason:** {reason}")

except Exception as e:
    st.error(f"Something went wrong:\n{str(e)}")
