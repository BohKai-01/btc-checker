import requests
import pandas as pd
import datetime
import streamlit as st

# --- CoinGecko Fetch ---
def fetch_coingecko_data(days=200):
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
        raise KeyError("Key 'prices' not found in API response. Full response:\n" + str(data))
    
    prices = data['prices']

    df = pd.DataFrame(prices, columns=['timestamp', 'price'])
    df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('Date', inplace=True)
    df.drop('timestamp', axis=1, inplace=True)
    df.rename(columns={'price': 'Close'}, inplace=True)
    return df

# --- Binance Fetch ---
def fetch_binance_data():
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    response = requests.get(url)
    data = response.json()
    return float(data['price'])

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

# --- Signal Logic ---
def generate_signal(rsi, price, sma50, sma200, macd, macd_signal):
    # Sell Signal
    if macd < macd_signal and (
        rsi > 65 or (price > sma50 and price > sma200)
    ):
        reason = f"MACD = {macd:.4f} < Signal = {macd_signal:.4f}, RSI = {rsi:.2f} or price over SMA50/SMA200 → Bearish setup"
        return "🔻 Sell Signal - Sell all", reason

    # Buy Signal
    elif (
        macd > macd_signal and
        rsi < 35 and
        price < sma50 and price > sma200
    ):
        reason = f"MACD = {macd:.4f} > Signal = {macd_signal:.4f}, RSI = {rsi:.2f}, Price < SMA50 but > SMA200 → Strong buy"
        return "🟢 Buy Signal - Invest all", reason

    # Cautious Buy Zone
    elif (
        35 <= rsi < 45 and
        price <= sma50 and
        macd > macd_signal
    ):
        reason = f"RSI = {rsi:.2f} (35–45), MACD = {macd:.4f} > Signal = {macd_signal:.4f} → Gradual buying zone"
        return "🟡 Building Buy Zone - Invest slowly", reason

    # Default
    else:
        reason = f"MACD = {macd:.4f}, RSI = {rsi:.2f}, Price = ${price:.2f} → No strong alignment"
        return "⚪ Neutral/Wait - Hold cash", reason

# --- Streamlit UI ---
st.set_page_config(page_title="BTC Buy/Sell Signal", layout="centered")
st.title("🧠 Bitcoin Buy/Sell Signal App")

# Input for current BTC price from eToro
etoro_price = st.number_input("🔢 Enter current BTC price from eToro (USD):", value=93187.39)

# Fetch data from CoinGecko and Binance
try:
    coingecko_df = fetch_coingecko_data()
    coingecko_latest = coingecko_df.iloc[-1]
    binance_price = fetch_binance_data()

    # Calculate indicators for CoinGecko data
    coingecko_df = calculate_indicators(coingecko_df)
    coingecko_latest = coingecko_df.iloc[-1]

    # Calculate percentage difference between eToro price and other platforms
    coingecko_diff = (etoro_price - coingecko_latest['Close']) / coingecko_latest['Close'] * 100
    binance_diff = (etoro_price - binance_price) / binance_price * 100

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(f"**Date/Time:** {now}")
    st.markdown(f"**eToro BTC Price:** ${etoro_price:.2f}")
    st.markdown(f"**CoinGecko BTC Price:** ${coingecko_latest['Close']:.2f}")
    st.markdown(f"**Binance BTC Price:** ${binance_price:.2f}")
    st.markdown(f"**CoinGecko vs eToro:** {coingecko_diff:.2f}% difference")
    st.markdown(f"**Binance vs eToro:** {binance_diff:.2f}% difference")

    st.markdown(f"**RSI (14-day):** {coingecko_latest['RSI']:.2f}")
    st.markdown(f"**SMA 50:** ${coingecko_latest['SMA_50']:.2f}")
    st.markdown(f"**SMA 200:** ${coingecko_latest['SMA_200']:.2f}")
    st.markdown(f"**MACD:** {coingecko_latest['MACD']:.4f}")
    st.markdown(f"**MACD Signal:** {coingecko_latest['MACD_Signal']:.4f}")

    signal, reason = generate_signal(coingecko_latest['RSI'], etoro_price, coingecko_latest['SMA_50'], coingecko_latest['SMA_200'], coingecko_latest['MACD'], coingecko_latest['MACD_Signal'])

    st.markdown("---")
    st.subheader(f"📢 {signal}")
    st.markdown(f"**🧠 Reason:** {reason}")

except Exception as e:
    st.error(f"Something went wrong: {e}")
