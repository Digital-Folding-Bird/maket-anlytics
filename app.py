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

# 页面基础配置 (宽屏模式)
st.set_page_config(
    page_title="多资产结构化交易与风控终端",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 强制应用炫酷暗黑主题，确保指标卡片和文字高亮清晰
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #e6edf3;
    }
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏：资产与策略配置
st.sidebar.title("🛠️ 资产与风控策略配置")
asset_category = st.sidebar.selectbox("资产大类", ["加密货币 (Crypto)", "大宗商品与美股 (YFinance)"])

if asset_category == "加密货币 (Crypto)":
    symbol_map = {
        "BTC/USDT": "BTC-USD",
        "ETH/USDT": "ETH-USD",
        "SOL/USDT": "SOL-USD",
        "BNB/USDT": "BNB-USD"
    }
    selected_display = st.sidebar.selectbox("交易对", list(symbol_map.keys()))
    symbol = symbol_map[selected_display]
else:
    selected_display = st.sidebar.selectbox("标的", ["GC=F", "SI=F", "CL=F", "SPY", "QQQ"])
    symbol = selected_display

timeframe = st.sidebar.selectbox("周期", ["1d", "1wk"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 仓位与风控参数")
risk_reward_ratio = st.sidebar.slider("目标盈亏比 (R:R)", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
stop_loss_pct = st.sidebar.slider("自定义止损幅度 (%)", min_value=1.0, max_value=10.0, value=3.0, step=0.5) / 100.0

# 数据获取函数
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

df = fetch_market_data(symbol, timeframe)
display_name = selected_display

# 主界面渲染
if not df.empty and len(df) > 10:
    # 纯 Pandas 计算指标
    df['EMA7'] = df['close'].ewm(span=7, adjust=False).mean()
    df['EMA25'] = df['close'].ewm(span=25, adjust=False).mean()
    df['SMA50'] = df['close'].rolling(window=50).mean()
    
    current_close = float(df['close'].iloc[-1])
    prev_ema7 = float(df['EMA7'].iloc[-2])
    curr_ema7 = float(df['EMA7'].iloc[-1])
    sma50_val = float(df['SMA50'].iloc[-1]) if not pd.isna(df['SMA50'].iloc[-1]) else current_close

    st.title(f"📊 {display_name} 结构化交易与风控终端")
    
    # 核心指标卡片（文字加粗、带高亮色，彻底解决看不清的问题）
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div style="color: #8b949e; font-size: 14px;">最新价格</div>
            <div style="color: #58a6ff; font-size: 24px; font-weight: bold;">{current_close:.2f}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        delta_val = curr_ema7 - prev_ema7
        color_code = "#3fb950" if delta_val >= 0 else "#f85149"
        st.markdown(f"""<div class="metric-card">
            <div style="color: #8b949e; font-size: 14px;">7日 EMA</div>
            <div style="color: {color_code}; font-size: 24px; font-weight: bold;">{curr_ema7:.2f}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div style="color: #8b949e; font-size: 14px;">50日 SMA</div>
            <div style="color: #d2a8ff; font-size: 24px; font-weight: bold;">{sma50_val:.2f}</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        trend_status = "📈 多头趋势" if curr_ema7 > sma50_val else "📉 空头趋势"
        trend_color = "#3fb950" if curr_ema7 > sma50_val else "#f85149"
        st.markdown(f"""<div class="metric-card">
            <div style="color: #8b949e; font-size: 14px;">结构状态</div>
            <div style="color: {trend_color}; font-size: 22px; font-weight: bold;">{trend_status}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # 止盈止损与交易策略推演模块
    st.subheader("🛡️ 动态止盈止损与仓位推演 (多头策略示例)")
    long_sl = current_close * (1 - stop_loss_pct)
    long_tp = current_close + (current_close - long_sl) * risk_reward_ratio
    
    short_sl = current_close * (1 + stop_loss_pct)
    short_tp = current_close - (short_sl - current_close) * risk_reward_ratio

    p1, p2 = st.columns(2)
    with p1:
        st.markdown(f"""
        * **🟢 做多参考价 (Long Entry)**: `{current_close:.2f}`
        * **🛑 建议止损位 (Stop Loss)**: `{long_sl:.2f}` (-{stop_loss_pct*100}%)
        * **🎯 目标止盈位 (Take Profit)**: `{long_tp:.2f}` (盈亏比 1:{risk_reward_ratio})
        """)
    with p2:
        st.markdown(f"""
        * **🔴 做空参考价 (Short Entry)**: `{current_close:.2f}`
        * **🛑 建议止损位 (Stop Loss)**: `{short_sl:.2f}` (+{stop_loss_pct*100}%)
        * **🎯 目标止盈位 (Take Profit)**: `{short_tp:.2f}` (盈亏比 1:{risk_reward_ratio})
        """)

    st.markdown("---")

    # Plotly 交互图表
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.75, 0.25])
    
    # K线
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='K线'
    ), row=1, col=1)
    
    # 均线
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA7'], line=dict(color='#ff9900', width=1.5), name='EMA7'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA25'], line=dict(color='#00ccff', width=1.5), name='EMA25'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='#d2a8ff', width=1.5, dash='dot'), name='SMA50'), row=1, col=1)
    
    # 成交量
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], marker_color='#8b949e', name='成交量'), row=2, col=1)
    
    fig.update_layout(
        template="plotly_dark", 
        height=650, 
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True, key="main_chart")

else:
    st.warning(f"⚠️ 暂未成功拉取到 {display_name} 的实时行情，请点击下方按钮重试。")
    if st.button("🔄 重新尝试连接"):
        st.cache_data.clear()
        st.rerun()