import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    # 映射为 yfinance 的加密货币符号，完全避开币安云端封锁
    symbol_map = {
        "BTC/USDT": "BTC-USD",
        "ETH/USDT": "ETH-USD",
        "SOL/USDT": "SOL-USD",
        "BNB/USDT": "BNB-USD"
    }
    selected_display = st.sidebar.selectbox("交易对", list(symbol_map.keys()))
    symbol = symbol_map[selected_display]
    timeframe = st.sidebar.selectbox("周期", ["1d", "1wk"], index=0)
else:
    selected_display = st.sidebar.selectbox("标的", ["GC=F", "SI=F", "CL=F", "SPY", "QQQ"]) # 黄金、白银、原油、标普500、纳斯达克
    symbol = selected_display
    timeframe = st.sidebar.selectbox("周期", ["1d", "1wk"], index=0)

# 通用稳定数据获取函数 (基于 yfinance，完美适配云端)
@st.cache_data(ttl=300)
def fetch_market_data(sym, tf):
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
df = fetch_market_data(symbol, timeframe)

# 主界面渲染
display_name = selected_display
if not df.empty and len(df) > 10:
    # 纯 Pandas 原生计算技术指标
    df['EMA7'] = df['close'].ewm(span=7, adjust=False).mean()
    df['EMA25'] = df['close'].ewm(span=25, adjust=False).mean()
    df['SMA50'] = df['close'].rolling(window=50).mean()
    
    current_close = float(df['close'].iloc[-1])
    prev_ema7 = float(df['EMA7'].iloc[-2])
    curr_ema7 = float(df['EMA7'].iloc[-1])
    
    st.title(f"📊 {display_name} 结构化交易仪表盘")
    
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
    st.warning(f"⚠️ 暂未成功拉取到 {display_name} 的实时行情，请点击下方按钮重试。")
    if st.button("🔄 重新尝试连接"):
        st.cache_data.clear()
        st.rerun()