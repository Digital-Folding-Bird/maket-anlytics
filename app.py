import streamlit as st
import pandas as pd
import numpy as np
import ccxt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# 安全导入 yfinance
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

# 页面基础配置
st.set_page_config(
    page_title="多资产结构化交易终端",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义暗黑主题样式
st.markdown("""
<style>
.main {
    background-color: #0e1117;
    color: #fafafa;
}
.stMetric {
    background-color: #161b22;
    padding: 10px;
    border-radius: 6px;
    border: 1px solid #30363d;
}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("🛠️ 资产与策略配置")
asset_category = st.sidebar.selectbox("资产大类", ["加密货币 (Crypto)", "大宗商品与美股 (YFinance)"])

if asset_category == "加密货币 (Crypto)":
    symbol = st.sidebar.selectbox("交易对", ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"])
    timeframe = st.sidebar.selectbox("周期", ["1h", "4h", "1d"], index=1)
else:
    symbol = st.sidebar.selectbox("标的", ["GC=F", "SI=F", "CL=F", "SPY", "QQQ"]) # 黄金、白银、原油、标普500、纳斯达克
    timeframe = st.sidebar.selectbox("周期", ["1d", "1wk"], index=0)

# 数据获取函数 (加密货币)
@st.cache_data(ttl=300)
def fetch_crypto_data(sym, tf, limit=150):
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(sym, timeframe=tf, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        return pd.DataFrame()

# 数据获取函数 (大宗/美股)
@st.cache_data(ttl=300)
def fetch_yf_data(sym, tf):
    if not HAS_YFINANCE:
        return pd.DataFrame()
    try:
        period = "6mo" if tf == "1d" else "2y"
        interval = "1d" if tf == "1d" else "1wk"
        df = yf.download(sym, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        return df[['open', 'high', 'low', 'close', 'volume']].dropna()
    except Exception as e:
        return pd.DataFrame()

# 加载数据
if asset_category == "加密货币 (Crypto)":
    df = fetch_crypto_data(symbol, timeframe)
else:
    df = fetch_yf_data(symbol, timeframe)

# 主界面渲染
if not df.empty and len(df) > 20:
    # 纯 Pandas 原生计算技术指标（绝对不报错）
    df['EMA7'] = df['close'].ewm(span=7, adjust=False).mean()
    df['EMA25'] = df['close'].ewm(span=25, adjust=False).mean()
    df['SMA50'] = df['close'].rolling(window=50).mean()
    
    current_close = float(df['close'].iloc[-1])
    prev_ema7 = float(df['EMA7'].iloc[-2])
    curr_ema7 = float(df['EMA7'].iloc[-1])
    
    st.title(f"📊 {symbol} 结构化交易仪表盘")
    
    # 核心指标展示
    col1, col2, col3 = st.columns(3)
    col1.metric("最新价格", f"{current_close:.2f}")
    col2.metric("7日 EMA", f"{curr_ema7:.2f}", delta=f"{curr_ema7 - prev_ema7:.2f}")
    sma50_val = df['SMA50'].iloc[-1]
    col3.metric("50日 SMA", f"{sma50_val:.2f}" if not pd.isna(sma50_val) else "N/A")

    # Plotly 交互子图表
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.7, 0.3])
    
    # K线主图
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='K线'
    ), row=1, col=1)
    
    # 均线
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA7'], line=dict(color='#ff9900', width=1.5), name='EMA7'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA25'], line=dict(color='#00ccff', width=1.5), name='EMA25'), row=1, col=1)
    
    # 成交量副图
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], marker_color='#555555', name='成交量'), row=2, col=1)
    
    fig.update_layout(
        template="plotly_dark", 
        height=600, 
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False
    )
    
    st.plotly_chart(fig, use_container_width=True, key="main_chart")

else:
    st.warning(f"⚠️ 暂未成功拉取到 {symbol} 的实时行情，可能是网络延迟或接口限制。")
    if st.button("🔄 重新尝试连接"):
        st.cache_data.clear()
        st.rerun()