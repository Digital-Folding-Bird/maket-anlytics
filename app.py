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
    page_title="多资产永续合约量化风控终端",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 强制应用炫酷暗黑主题
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

# 侧边栏：资产配置
st.sidebar.title("🛠️ 资产与合约风控配置")
asset_category = st.sidebar.selectbox("资产大类", ["加密货币 (Crypto)", "大宗商品与美股 / 自定义输入"])

# 定义 20 只主流加密货币列表
crypto_top_20 = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", 
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "SUI-USD", 
    "DOT-USD", "NEAR-USD", "MATIC-USD", "LTC-USD", "UNI-USD", 
    "ATOM-USD", "APT-USD", "ETC-USD", "ICP-USD", "FIL-USD"
]

# 定义主流大宗商品与美股
common_yfinance = [
    "GC=F",   # 黄金期货
    "SI=F",   # 白银期货
    "CL=F",   # WTI原油期货
    "BZ=F",   # 布伦特原油
    "NG=F",   # 天然气
    "PL=F",   # 铂金
    "PA=F",   # 钯金
    "SPY",    # 标普500 ETF
    "QQQ",    # 纳斯达克100 ETF
    "AAPL",   # 苹果
    "MSFT",   # 微软
    "NVDA",   # 英伟达
    "TSLA"    # 特斯拉
]

if asset_category == "加密货币 (Crypto)":
    selected_crypto = st.sidebar.selectbox("主流20只加密货币", crypto_top_20)
    custom_input = st.sidebar.text_input("或者手动输入自定义代码 (如 RENDER-USD)", value="")
    symbol = custom_input.strip() if custom_input.strip() else selected_crypto
    display_name = symbol
else:
    selected_asset = st.sidebar.selectbox("主流大宗与美股", common_yfinance)
    custom_input = st.sidebar.text_input("或者手动输入自定义代码 (如 BABA, HG=F)", value="")
    symbol = custom_input.strip() if custom_input.strip() else selected_asset
    display_name = symbol

timeframe = st.sidebar.selectbox("周期", ["1d", "1wk"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 永续合约模拟参数 (50U 计划)")
direction = st.sidebar.radio("交易方向", ["🟢 做多 (Long)", "🔴 做空 (Short)"], index=0)
margin_usdt = st.sidebar.number_input("投入保证金 (USDT)", min_value=10.0, max_value=1000.0, value=50.0, step=10.0)
leverage = st.sidebar.slider("合约杠杆倍数 (Leverage)", min_value=1, max_value=50, value=10, step=1)
risk_reward_ratio = st.sidebar.slider("目标盈亏比 (R:R)", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
stop_loss_pct = st.sidebar.slider("止损幅度 (%)", min_value=1.0, max_value=15.0, value=3.0, step=0.5) / 100.0

# 数据获取函数
@st.cache_data(ttl=300)
def fetch_market_data(sym, tf):
    if not HAS_YFINANCE:
        return pd.DataFrame()
    try:
        period = "6mo" if tf == "1d" else "2y"
        interval = "1d" if tf == "1d" else "1wk"
        df = yf.download(sym, period=period, interval=interval, progress=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        return df[['open', 'high', 'low', 'close', 'volume']].dropna()
    except Exception as e:
        return pd.DataFrame()

df = fetch_market_data(symbol, timeframe)

# 主界面渲染
if not df.empty and len(df) > 5:
    # 纯 Pandas 计算指标
    df['EMA7'] = df['close'].ewm(span=7, adjust=False).mean()
    df['EMA25'] = df['close'].ewm(span=25, adjust=False).mean()
    df['SMA50'] = df['close'].rolling(window=50).mean()
    
    current_close = float(df['close'].iloc[-1])
    prev_ema7 = float(df['EMA7'].iloc[-2]) if len(df) > 1 else current_close
    curr_ema7 = float(df['EMA7'].iloc[-1])
    sma50_val = float(df['SMA50'].iloc[-1]) if not pd.isna(df['SMA50'].iloc[-1]) else current_close

    st.title(f"📊 {display_name} 永续合约量化交易终端")
    
    # 核心指标卡片
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
        trend_status = "📈 多头结构" if curr_ema7 > sma50_val else "📉 空头结构"
        trend_color = "#3fb950" if curr_ema7 > sma50_val else "#f85149"
        st.markdown(f"""<div class="metric-card">
            <div style="color: #8b949e; font-size: 14px;">均线结构判断</div>
            <div style="color: {trend_color}; font-size: 22px; font-weight: bold;">{trend_status}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # 永续合约仓位与风控推演计算
    total_position_value = margin_usdt * leverage # 总仓位价值 (名义价值)
    coin_amount = total_position_value / current_close # 持有币量
    
    is_long = "做多" in direction
    if is_long:
        entry_price = current_close
        stop_loss_price = entry_price * (1 - stop_loss_pct)
        take_profit_price = entry_price + (entry_price - stop_loss_price) * risk_reward_ratio
        # 简单估算爆仓价（预留约 0.5% 维持保证金率）
        liquidation_price = entry_price * (1 - (1 / leverage) * 0.95)
        max_loss_usdt = total_position_value * stop_loss_pct
        target_profit_usdt = max_loss_usdt * risk_reward_ratio
    else:
        entry_price = current_close
        stop_loss_price = entry_price * (1 + stop_loss_pct)
        take_profit_price = entry_price - (stop_loss_price - entry_price) * risk_reward_ratio
        liquidation_price = entry_price * (1 + (1 / leverage) * 0.95)
        max_loss_usdt = total_position_value * stop_loss_pct
        target_profit_usdt = max_loss_usdt * risk_reward_ratio

    st.subheader(f"🎯 永续合约模拟看板 ({margin_usdt}U 保证金 × {leverage}x 杠杆 | {direction})")
    
    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown(f"""
        * **💰 投入保证金**: `{margin_usdt:.1f} USDT`
        * **⚡ 合约杠杆**: `{leverage} 倍`
        * **📦 总持仓名义价值**: `{total_position_value:.2f} USDT`
        * **🪙 预计建仓数量**: `{coin_amount:.4f}` 币
        """)
    with r2:
        st.markdown(f"""
        * **📍 开仓均价 (Entry)**: `{entry_price:.2f}`
        * **🛑 计划止损价 (SL)**: `{stop_loss_price:.2f}` (-{stop_loss_pct*100}%)
        * **🎯 计划止盈价 (TP)**: `{take_profit_price:.2f}` (盈亏比 1:{risk_reward_ratio})
        """)
    with r3:
        # 预警：如果止损亏损大于保证金，说明爆仓在止损之前
        is_liq_risk = (is_long and stop_loss_price <= liquidation_price) or (not is_long and stop_loss_price >= liquidation_price)
        liq_color = "#f85149" if leverage >= 20 else "#3fb950"
        st.markdown(f"""
        * **⚠️ 预估爆仓价 (Liq. Price)**: <span style="color: {liq_color}; font-weight: bold;">`{liquidation_price:.2f}`</span>
        * **🔻 若触发止损将亏损**: `≈ -{min(max_loss_usdt, margin_usdt):.2f} USDT`
        * **📈 若触发止盈将盈利**: `≈ +{target_profit_usdt:.2f} USDT`
        """)
        
    if leverage >= 20:
        st.warning("⚠️ **高杠杆警示**：当前杠杆偏高（≥20x），加密市场波动剧烈，极易触发插针爆仓，请注意控制风险！")

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
    
    # 在主图上画出开仓价、止损价、止盈价和爆仓价水平线
    fig.add_hline(y=entry_price, line_dash="dash", line_color="blue", annotation_text=f"开仓价: {entry_price:.2f}", row=1, col=1)
    fig.add_hline(y=stop_loss_price, line_dash="solid", line_color="red", annotation_text=f"止损价: {stop_loss_price:.2f}", row=1, col=1)
    fig.add_hline(y=take_profit_price, line_dash="solid", line_color="green", annotation_text=f"止盈价: {take_profit_price:.2f}", row=1, col=1)
    fig.add_hline(y=liquidation_price, line_dash="dot", line_color="orange", annotation_text=f"预估爆仓价: {liquidation_price:.2f}", row=1, col=1)

    # 成交量
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], marker_color='#8b949e', name='成交量'), row=2, col=1)
    
    fig.update_layout(
        template="plotly_dark", 
        height=680, 
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True, key="main_chart")

else:
    st.warning(f"⚠️ 无法获取到标的 **{display_name}** 的行情，请检查侧边栏输入。")
    if st.button("🔄 重新尝试连接"):
        st.cache_data.clear()
        st.rerun()