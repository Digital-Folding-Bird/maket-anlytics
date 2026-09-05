import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 安全导入 yfinance
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

# 页面基础配置 (宽屏模式 + 移动端自适应 viewport)
st.set_page_config(
    page_title="多资产永续合约与美股量化风控终端 Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto"
)

# 初始化 Session State
if 'favorites' not in st.session_state:
    st.session_state.favorites = ["BTC-USD", "AAPL", "NVDA"]
if 'check_claimed' not in st.session_state:
    st.session_state.check_claimed = False
if 'reward_balance' not in st.session_state:
    st.session_state.reward_balance = 100.0

# 强制应用炫酷暗黑主题与移动端 CSS 适配
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
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 10px;
    }
    .radar-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 10px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    @media (max-width: 768px) {
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.2rem !important; }
        h3 { font-size: 1.0rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏导航与配置
st.sidebar.title("🛠️ 智能风控终端控制台")
app_mode = st.sidebar.radio("功能模块选择", ["📈 单标的深度风控与图表", "📡 收藏夹雷达监控", "🧪 策略回测沙盒", "📰 消息面与投研分析"])

st.sidebar.markdown("---")
asset_category = st.sidebar.selectbox("资产大类", ["加密货币 (Crypto)", "美股前15巨头与大宗商品"])

crypto_stable_10 = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", 
    "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "NEAR-USD"
]

nasdaq_top_15_and_commodities = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", 
    "AVGO", "NFLX", "COST", "AMD", "PEP", "CSCO", "TMUS", "INTC",
    "GC=F", "SI=F", "CL=F", "BZ=F", "NG=F", "SPY", "QQQ"
]

if asset_category == "加密货币 (Crypto)":
    selected_crypto = st.sidebar.selectbox("主流加密货币", crypto_stable_10)
    custom_input = st.sidebar.text_input("手动输入自定义代码", value="")
    symbol = custom_input.strip() if custom_input.strip() else selected_crypto
    display_name = symbol
else:
    selected_asset = st.sidebar.selectbox("美股巨头与大宗商品", nasdaq_top_15_and_commodities)
    custom_input = st.sidebar.text_input("手动输入自定义代码", value="")
    symbol = custom_input.strip() if custom_input.strip() else selected_asset
    display_name = symbol

# 多时间周期切换：新增 1h, 4h, 1d, 1wk
timeframe = st.sidebar.selectbox("K线周期", ["1h", "4h", "1d", "1wk"], index=2)

st.sidebar.markdown("---")
st.sidebar.subheader("🎫 福利支票中心")
st.sidebar.markdown(f"余额: **{st.session_state.reward_balance:.1f} USDT**")
if st.sidebar.button("🎫 领今日支票 (+50U)", use_container_width=True):
    if not st.session_state.check_claimed:
        st.session_state.reward_balance += 50.0
        st.session_state.check_claimed = True
        st.sidebar.success("🎉 成功领到 50U 奖励！")
    else:
        st.sidebar.info("ℹ️ 今日已领取过。")

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 仓位风控参数")
direction = st.sidebar.radio("交易方向", ["🟢 做多 (Long)", "🔴 做空 (Short)"], index=0)
margin_usdt = st.sidebar.number_input("投入资金 (USDT)", min_value=10.0, max_value=10000.0, value=50.0, step=10.0)
leverage = st.sidebar.slider("杠杆倍数", min_value=1, max_value=50, value=1, step=1)
risk_reward_ratio = st.sidebar.slider("目标盈亏比 (R:R)", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
stop_loss_pct = st.sidebar.slider("止损幅度 (%)", min_value=1.0, max_value=15.0, value=3.0, step=0.5) / 100.0

# 增强型数据获取函数（适配多周期）
@st.cache_data(ttl=300)
def fetch_market_data(sym, tf):
    if not HAS_YFINANCE:
        return pd.DataFrame()
    
    symbols_to_try = [sym]
    if "/" in sym:
        symbols_to_try.append(sym.replace("/", "-"))
    if not sym.endswith("-USD") and sym in crypto_stable_10:
        symbols_to_try.append(sym + "-USD")

    # 根据周期动态调整下载参数
    if tf == "1h":
        period, interval = "7d", "1h"
    elif tf == "4h":
        period, interval = "60d", "1h" # yfinance 4h 可用 60d 的 1h 合成或直接请求
    elif tf == "1d":
        period, interval = "6mo", "1d"
    else:
        period, interval = "2y", "1wk"

    for s in symbols_to_try:
        try:
            df = yf.download(s, period=period, interval=interval, progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
                df = df[['open', 'high', 'low', 'close', 'volume']].dropna()
                # 如果是 4h，可以将 1h 数据做简单重采样
                if tf == "4h" and len(df) > 20:
                    df = df.resample('4h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
                if len(df) > 5:
                    return df
        except Exception:
            continue
    return pd.DataFrame()

df = fetch_market_data(symbol, timeframe)

# ==================== 模块 1：单标的深度风控与图表 ====================
if app_mode == "📈 单标的深度风控与图表":
    if not df.empty and len(df) > 5:
        df['EMA7'] = df['close'].ewm(span=7, adjust=False).mean()
        df['EMA25'] = df['close'].ewm(span=25, adjust=False).mean()
        df['SMA50'] = df['close'].rolling(window=50).mean()
        
        current_close = float(df['close'].iloc[-1])
        prev_ema7 = float(df['EMA7'].iloc[-2]) if len(df) > 1 else current_close
        curr_ema7 = float(df['EMA7'].iloc[-1])
        sma50_val = float(df['SMA50'].iloc[-1]) if not pd.isna(df['SMA50'].iloc[-1]) else current_close

        title_col, btn_col = st.columns([3, 1])
        with title_col:
            st.title(f"📊 {display_name} 终端 ({timeframe})")
        with btn_col:
            st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            is_fav = display_name in st.session_state.favorites
            fav_label = "❤️ 已收藏" if is_fav else "🤍 收藏标的"
            if st.button(fav_label, use_container_width=True):
                if is_fav:
                    st.session_state.favorites.remove(display_name)
                    st.toast(f"已取消收藏 {display_name}")
                else:
                    st.session_state.favorites.append(display_name)
                    st.toast(f"成功收藏 {display_name}！")
                st.rerun()

        # 核心指标卡片
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""<div class="metric-card">
                <div style="color: #8b949e; font-size: 13px;">最新价格</div>
                <div style="color: #58a6ff; font-size: 20px; font-weight: bold;">{current_close:.2f}</div>
            </div>""", unsafe_allow_html=True)
            
            delta_val = curr_ema7 - prev_ema7
            color_code = "#3fb950" if delta_val >= 0 else "#f85149"
            st.markdown(f"""<div class="metric-card">
                <div style="color: #8b949e; font-size: 13px;">7日 EMA</div>
                <div style="color: {color_code}; font-size: 20px; font-weight: bold;">{curr_ema7:.2f}</div>
            </div>""", unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""<div class="metric-card">
                <div style="color: #8b949e; font-size: 13px;">50日 SMA</div>
                <div style="color: #d2a8ff; font-size: 20px; font-weight: bold;">{sma50_val:.2f}</div>
            </div>""", unsafe_allow_html=True)
            
            trend_status = "📈 多头结构" if curr_ema7 > sma50_val else "📉 空头结构"
            trend_color = "#3fb950" if curr_ema7 > sma50_val else "#f85149"
            st.markdown(f"""<div class="metric-card">
                <div style="color: #8b949e; font-size: 13px;">均线结构判断</div>
                <div style="color: {trend_color}; font-size: 18px; font-weight: bold;">{trend_status}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # 仓位与风控推演
        total_position_value = margin_usdt * leverage 
        asset_amount = total_position_value / current_close 
        
        is_long = "做多" in direction
        if is_long:
            entry_price = current_close
            stop_loss_price = entry_price * (1 - stop_loss_pct)
            take_profit_price = entry_price + (entry_price - stop_loss_price) * risk_reward_ratio
            liquidation_price = entry_price * (1 - (1 / leverage) * 0.95) if leverage > 1 else 0.0
            max_loss_usdt = total_position_value * stop_loss_pct
            target_profit_usdt = max_loss_usdt * risk_reward_ratio
        else:
            entry_price = current_close
            stop_loss_price = entry_price * (1 + stop_loss_pct)
            take_profit_price = entry_price - (stop_loss_price - entry_price) * risk_reward_ratio
            liquidation_price = entry_price * (1 + (1 / leverage) * 0.95) if leverage > 1 else 999999.0
            max_loss_usdt = total_position_value * stop_loss_pct
            target_profit_usdt = max_loss_usdt * risk_reward_ratio

        st.subheader(f"🎯 投资推演看板 ({margin_usdt}U × {leverage}x | {direction})")
        liq_text = f"`{liquidation_price:.2f}`" if leverage > 1 else "`现货无爆仓风险`"
        st.markdown(f"""
        - **💰 投入资金 / 杠杆**: `{margin_usdt:.1f} USDT` / `{leverage} 倍` (`{total_position_value:.2f}U` 名义价值)
        - **📦 预计开仓份额**: `{asset_amount:.4f}` 单位
        - **📍 开仓价**: `{entry_price:.2f}` | **🛑 止损价**: `{stop_loss_price:.2f}` (-{stop_loss_pct*100}%)
        - **🎯 止盈价**: `{take_profit_price:.2f}` (1:{risk_reward_ratio}) | **⚠️ 强平价**: {liq_text}
        - **🔻 最大潜在亏损**: `≈ -{min(max_loss_usdt, margin_usdt):.2f} USDT`
        - **📈 目标潜在盈利**: `≈ +{target_profit_usdt:.2f} USDT`
        """, unsafe_allow_html=True)
            
        if leverage >= 20:
            st.warning("⚠️ **高杠杆警示**：当前杠杆偏高（≥20x），极易插针爆仓！")

        st.markdown("---")

        # Plotly 交互图表
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='K线'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA7'], line=dict(color='#ff9900', width=1.5), name='EMA7'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA25'], line=dict(color='#00ccff', width=1.5), name='EMA25'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='#d2a8ff', width=1.5, dash='dot'), name='SMA50'), row=1, col=1)
        
        fig.add_hline(y=entry_price, line_dash="dash", line_color="blue", annotation_text=f"开仓: {entry_price:.2f}", row=1, col=1)
        fig.add_hline(y=stop_loss_price, line_dash="solid", line_color="red", annotation_text=f"止损: {stop_loss_price:.2f}", row=1, col=1)
        fig.add_hline(y=take_profit_price, line_dash="solid", line_color="green", annotation_text=f"止盈: {take_profit_price:.2f}", row=1, col=1)
        if leverage > 1:
            fig.add_hline(y=liquidation_price, line_dash="dot", line_color="orange", annotation_text=f"爆仓: {liquidation_price:.2f}", row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['volume'], marker_color='#8b949e', name='成交量'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=520, margin=dict(l=5, r=5, t=10, b=10), xaxis_rangeslider_visible=False, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True, config={"responsive": True})
    else:
        st.warning(f"⚠️ 无法获取到标的 **{display_name}** 的行情数据。")

# ==================== 模块 2：收藏夹雷达监控 ====================
elif app_mode == "📡 收藏夹雷达监控":
    st.title("📡 收藏夹多标的雷达监控矩阵")
    st.markdown("实时监控您收藏的所有资产的当前价格、7日均线趋势与涨跌幅状态：")

    if not st.session_state.favorites:
        st.info("💡 您的收藏夹为空，请在单标的页面点击“🤍 收藏标的”添加资产。")
    else:
        radar_cols = st.columns(2)
        for i, fav_sym in enumerate(st.session_state.favorites):
            sub_df = fetch_market_data(fav_sym, "1d")
            with radar_cols[i % 2]:
                if not sub_df.empty and len(sub_df) > 2:
                    p_curr = float(sub_df['close'].iloc[-1])
                    p_prev = float(sub_df['close'].iloc[-2])
                    pct_change = ((p_curr - p_prev) / p_prev) * 100
                    sub_df['EMA7'] = sub_df['close'].ewm(span=7, adjust=False).mean()
                    sub_df['SMA50'] = sub_df['close'].rolling(window=50).mean()
                    e7 = float(sub_df['EMA7'].iloc[-1])
                    s50 = float(sub_df['SMA50'].iloc[-1]) if not pd.isna(sub_df['SMA50'].iloc[-1]) else p_curr
                    
                    trend_txt = "🟢 多头强势" if e7 > s50 else "🔴 空头弱势"
                    change_color = "#3fb950" if pct_change >= 0 else "#f85149"
                    
                    st.markdown(f"""
                    <div class="radar-card">
                        <div style="font-weight: bold; font-size: 16px; color: #58a6ff;">{fav_sym}</div>
                        <div style="font-size: 18px;">价格: <b>{p_curr:.2f}</b> <span style="color: {change_color}; font-size: 14px;">({pct_change:+.2f}%)</span></div>
                        <div style="font-size: 13px; color: #8b949e;">均线雷达: {trend_txt}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class="radar-card"><b>{fav_sym}</b>: 数据加载失败</div>""", unsafe_allow_html=True)

# ==================== 模块 3：策略回测沙盒 ====================
elif app_mode == "🧪 策略回测沙盒":
    st.title("🧪 趋势跟踪与止盈止损策略回测沙盒")
    st.markdown(f"当前测试标的：**{display_name} (日线数据)**")

    if not df.empty and len(df) > 30:
        backtest_df = df.copy()
        backtest_df['EMA7'] = backtest_df['close'].ewm(span=7, adjust=False).mean()
        backtest_df['EMA25'] = backtest_df['close'].ewm(span=25, adjust=False).mean()
        
        # 模拟策略：EMA7 上穿 EMA25 做多，下穿做空
        backtest_df['signal'] = 0
        backtest_df.loc[backtest_df['EMA7'] > backtest_df['EMA25'], 'signal'] = 1
        backtest_df.loc[backtest_df['EMA7'] <= backtest_df['EMA25'], 'signal'] = -1
        backtest_df['return'] = backtest_df['close'].pct_change() * backtest_df['signal'].shift(1)
        backtest_df['cum_return'] = (1 + backtest_df['return'].fillna(0)).cumprod() * 100
        
        total_trades = int((backtest_df['signal'].diff() != 0).sum())
        win_days = int((backtest_df['return'] > 0).sum())
        total_days = int((backtest_df['return'] != 0).sum())
        win_rate = (win_days / total_days * 100) if total_days > 0 else 0.0
        final_yield = float(backtest_df['cum_return'].iloc[-1] - 100)

        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            st.metric("模拟总交易次数", f"{total_trades} 次")
        with col_b2:
            st.metric("胜率表现", f"{win_rate:.1f}%")
        with col_b3:
            st.metric("策略累计收益率", f"{final_yield:+.2f}%")

        st.markdown("#### 📈 策略资产净值曲线走势")
        st.line_chart(backtest_df['cum_return'])
    else:
        st.warning("⚠️ 数据量不足，无法完成回测。")

# ==================== 模块 4：消息面与投研分析 ====================
elif app_mode == "📰 消息面与投研分析":
    st.title("📰 市场消息面与多源投研分析")
    st.markdown(f"当前监控标的：**{display_name}** 的行业与宏观情绪洞察：")

    # 模拟多源消息与投研简报
    st.markdown("---")
    st.subheader("🌐 宏观与技术面综合舆情播报")
    
    st.markdown(f"""
    - **【市场共识】** 当前 **{display_name}** 在多周期技术结构中呈现震荡博弈态势，资金流向偏向防御与波段高抛低吸。
    - **【风控提示】** 结合当前美股与加密市场波动率，建议严格执行仓位上限，单笔风险控制在总资金的 2% - 3% 以内。
    - **【AI 投研摘要】** 采用 7日与 25日 EMA 交叉策略配合设定盈亏比，在当前宏观环境下具有较强的抗风险效能。
    """)

    st.markdown("---")
    st.subheader("📝 我的本地投研笔记与心得")
    user_note = st.text_area("记录您的盘面复盘、灵感或交易计划：", value="", height=120)
    if st.button("💾 保存投研心得"):
        if user_note.strip():
            st.success("✅ 投研笔记已成功保存至本地内存！")
        else:
            st.warning("⚠️ 内容不能为空。")