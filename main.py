import requests
import pandas as pd
import datetime
import streamlit as st

# --- CoinGecko Fetch ---
def fetch_btc_data_coingecko(days=200):
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
def fetch_btc_data_binance(days=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": days
    }
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

    data = response.json()

    # Process Binance data to match the same structure as CoinGecko
    prices = [(item[0], item[4]) for item in data]  # Only taking the closing price
    df = pd.DataFrame(prices, columns=['timestamp', 'price'])
    df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('Date', inplace=True)
    df.drop('timestamp', axis=1, inplace=True)
    df.rename(columns={'price': 'Close'}, inplace=True)
    return df

# --- Wrapper to fetch data with fallback ---
def fetch_btc_data(days=200):
    try:
        # Try CoinGecko first
        return fetch_btc_data_coingecko(days), "CoinGecko"
    except Exception as e:
        if 'API Error: 429' in str(e):
            print("CoinGecko rate limit exceeded, falling back to Binance...")
            return fetch_btc_data_binance(days), "Binance"
        else:
            raise e

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

try:
    df, source = fetch_btc_data()
    df = calculate_indicators(df)
    latest = df.iloc[-1]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(f"**Date/Time:** {now}")
    st.markdown(f"**BTC Price:** ${etoro_price:.2f} (from eToro)")
    st.markdown(f"**Data Source:** {source}")
    st.markdown(f"**RSI (14-day):** {latest['RSI']:.2f}")
    st.markdown(f"**SMA 50:** ${latest['SMA_50']:.2f}")
    st.markdown(f"**SMA 200:** ${latest['SMA_200']:.2f}")
    st.markdown(f"**MACD:** {latest['MACD']:.4f}")
    st.markdown(f"**MACD Signal:** {latest['MACD_Signal']:.4f}")

    signal, reason = generate_signal(latest['RSI'], etoro_price, latest['SMA_50'], latest['SMA_200'], latest['MACD'], latest['MACD_Signal'])

    st.markdown("---")
    st.subheader(f"📢 {signal}")
    st.markdown(f"**🧠 Reason:** {reason}")

except Exception as e:
    st.error(f"Something went wrong: {e}")
