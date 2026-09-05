import streamlit as st
import pandas as pd
import numpy as np
import ccxt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta

# 尝试导入 yfinance 用于拉取美股和大宗商品行情
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

# 页面配置：移动端极简暗黑风格
st.set_page_config(
    page_title="多资产结构位合约终端", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# OKX 暗黑风格注入
st.markdown("""
<style>
    html, body, .stApp { background-color: #0b0e11 !important; }
    .block-container { padding: 0.3rem !important; }
    header[data-testid="stHeader"] { background-color: transparent !important; }
    .js-plotly-plot .plotly .draglayer { touch-action: none !important; }
    
    .okx-price-card {
        background: #181d24; border: 1px solid #2b313a; border-radius: 8px; padding: 8px 12px; margin-bottom: 6px;
    }
    .okx-price-title { font-size: 0.8rem; color: #848e9c; display: flex; justify-content: space-between; }
    .okx-price-value { font-size: 1.6rem; font-weight: 800; color: #0ecb81; margin-top: 2px; }
    .okx-price-down { color: #f6465d !important; }
    .time-badge { font-size: 0.7rem; background-color: #2b313a; color: #eaecef; padding: 2px 6px; border-radius: 4px; }
    
    .metrics-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-bottom: 6px; }
    .metric-card { background-color: #181d24; border: 1px solid #2b313a; border-radius: 6px; padding: 6px 8px; text-align: center; }
    .metric-label { font-size: 0.7rem; color: #848e9c; }
    .metric-val { font-size: 0.9rem; font-weight: bold; color: #eaecef; margin-top: 1px; }
    
    .futures-card {
        background-color: #111827; border: 1px solid #1e293b; border-left: 4px solid #38bdf8;
        border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; font-size: 0.82rem; line-height: 1.5; color: #eaecef;
    }
    .futures-title { font-size: 0.88rem; font-weight: bold; margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)

# ---------------- 侧边栏配置 ----------------
st.sidebar.title("⚙️ 合约交易控制台")

capital = st.sidebar.number_input("单笔保证金 (USDT)", value=50.0, step=5.0)
leverage = st.sidebar.slider("杠杆倍数 (Leverage)", min_value=2, max_value=20, value=5, step=1)
futures_fee_rate = st.sidebar.number_input("合约手续费率 (%)", value=0.05, step=0.01) / 100

# 完整的资产分类列表：贵金属、美股与科技股、数字货币
asset_categories = {
    "📈 美股与指数": [
        "QQQ | 纳斯达克100 ETF",
        "SPY | 标普500 ETF",
        "NVDA | 英伟达",
        "TSLA | 特斯拉",
        "AAPL | 苹果",
        "MSFT | 微软",
        "AMZN | 亚马逊",
        "GOOGL | 谷歌",
        "COIN | Coinbase"
    ],
    "🥇 贵金属与大宗商品": [
        "GOLD | 现货黄金 (GC=F)",
        "SILVER | 现货白银 (SI=F)",
        "OIL | 原油/WTI (CL=F)",
        "XAUT/USDT | Tether Gold"
    ],
    "🪙 数字货币": [
        "BTC/USDT | 比特币",
        "ETH/USDT | 以太坊",
        "SOL/USDT | Solana",
        "BNB/USDT | 币安币",
        "SUI/USDT | Sui",
        "DOGE/USDT | 狗狗币",
        "PEPE/USDT | Pepe",
        "XRP/USDT | 瑞波币",
        "NEAR/USDT | Near",
        "APT/USDT | Aptos"
    ],
    "✏️ 手动输入": [
        "✏️ 手动输入代码..."
    ]
}

selected_category = st.sidebar.selectbox("🏷️ 选择资产分类", list(asset_categories.keys()), index=0)
selected_item = st.sidebar.selectbox("📌 选择交易标的", asset_categories[selected_category], index=0)

if "手动" in selected_item:
    user_input = st.sidebar.text_input("输入交易对或代码 (如 NVDA 或 BTC/USDT)", value="NVDA").strip().upper()
    symbol = user_input
else:
    symbol = selected_item.split(" | ")[0].strip()

timeframe = st.sidebar.selectbox("K线周期", ["5m", "15m", "1h", "4h", "1d"], index=1)
risk_reward_ratio = st.sidebar.slider("目标最小盈亏比", 1.5, 4.0, 2.0, 0.5)

# ---------------- ⚡ 极速多源数据加载 ----------------
@st.cache_data(ttl=15, show_spinner=False)
def fetch_fast_ohlcv(sym, tf):
    # 映射特殊大宗商品代码
    yf_mapping = {
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "OIL": "CL=F",
        "USOIL": "CL=F"
    }
    
    ticker_code = yf_mapping.get(sym, sym)

    # 1. 如果是不含 '/' 的美股代码或期货代码，优先试用 Yahoo Finance
    if HAS_YFINANCE and ("/" not in sym or ticker_code.endswith("=F")):
        tf_map = {"5m": "5m", "15m": "15m", "1h": "60m", "4h": "60m", "1d": "1d"}
        yf_interval = tf_map.get(tf, "15m")
        period_map = {"5m": "5d", "15m": "7d", "1h": "1mo", "4h": "1mo", "1d": "1y"}
        
        try:
            ticker = yf.Ticker(ticker_code)
            data = ticker.history(period=period_map.get(tf, "7d"), interval=yf_interval)
            if not data.empty:
                data = data.reset_index()
                col_time = 'Datetime' if 'Datetime' in data.columns else 'Date'
                data[col_time] = pd.to_datetime(data[col_time]).dt.tz_convert('Asia/Shanghai')
                data = data.rename(columns={col_time: 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
                df_res = data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(80).reset_index(drop=True)
                return df_res, ticker_code
        except Exception:
            pass

    # 2. 数字货币使用 CCXT（OKX / Binance）获取
    search_symbols = [sym]
    if "XAU" in sym or "GOLD" in sym:
        search_symbols.extend(["XAUT/USDT", "PAXG/USDT"])
    elif "/" not in sym and not sym.endswith("=F"):
        search_symbols.append(f"{sym}/USDT")

    exchanges = [
        ("okx", ccxt.okx({'enableRateLimit': False, 'timeout': 1500})),
        ("binance", ccxt.binance({'enableRateLimit': False, 'timeout': 1500}))
    ]

    for s in search_symbols:
        for name, ex in exchanges:
            try:
                ohlcv = ex.fetch_ohlcv(s, timeframe=tf, limit=80)
                if ohlcv and len(ohlcv) > 0:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
                    return df, s
            except Exception:
                continue

    return pd.DataFrame(), sym

df, real_symbol = fetch_fast_ohlcv(symbol, timeframe)

if not df.empty and len(df) > 25:
    # 技术指标计算
    df['EMA7'] = ta.ema(df['close'], length=7)
    df['EMA20'] = ta.ema(df['close'], length=20)
    df['EMA50'] = ta.ema(df['close'], length=50)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['ADX'] = ta.adx(df['high'], df['low'], df['close'], length=14)['ADX_14']
    
    curr_price = float(df['close'].iloc[-1])
    prev_price = float(df['close'].iloc[-2])
    price_change_pct = ((curr_price - prev_price) / prev_price) * 100
    
    curr_ema7 = float(df['EMA7'].iloc[-1])
    curr_ema20 = float(df['EMA20'].iloc[-1])
    curr_adx = float(df['ADX'].iloc[-1])

    # 结构位计算（近 15 根 K 线）
    lookback = 15
    recent_low = float(df['low'].iloc[-lookback:-1].min())
    recent_high = float(df['high'].iloc[-lookback:-1].max())

    position_notional = capital * leverage

    # 趋势判定
    is_ranging = curr_adx < 20
    is_bullish = (curr_ema7 > curr_ema20) and (curr_price >= curr_ema20)
    is_bearish = (curr_ema7 < curr_ema20) and (curr_price < curr_ema20)

    if is_ranging:
        direction = "FLAT"
        status_text = "无结构/观望"
        action_color = "#848e9c"
        entry_price, sl_price, tp1_price, liq_price = curr_price, curr_price, curr_price, 0.0
        advice_msg = f"⚠️ 当前处于震荡盘整（ADX={curr_adx:.1f} < 20），结构破位风险较高，建议暂时观望。"
    elif is_bullish:
        direction = "LONG"
        status_text = f"做多 (Long {leverage}x)"
        action_color = "#0ecb81"
        
        entry_price = round(curr_price, 4)
        sl_price = round(recent_low * 0.997, 4)  # 结构支撑位下方 0.3%
        risk_per_unit = entry_price - sl_price
        tp1_price = round(entry_price + (risk_per_unit * risk_reward_ratio), 4)
        liq_price = round(entry_price * (1 - (1 / leverage) * 0.9), 4)
        
        advice_msg = f"🟢 **结构位多单**：依托前低支撑 **${recent_low:.4f}**，止损设在下方 **${sl_price}**；目标看至 **${tp1_price}**。"
    else:
        direction = "SHORT"
        status_text = f"做空 (Short {leverage}x)"
        action_color = "#f6465d"
        
        entry_price = round(curr_price, 4)
        sl_price = round(recent_high * 1.003, 4)  # 结构阻力位上方 0.3%
        risk_per_unit = sl_price - entry_price
        tp1_price = round(entry_price - (risk_per_unit * risk_reward_ratio), 4)
        liq_price = round(entry_price * (1 + (1 / leverage) * 0.9), 4)
        
        advice_msg = f"🔴 **结构位空单**：依托前高阻力 **${recent_high:.4f}**，止损设在上方 **${sl_price}**；目标看至 **${tp1_price}**。"

    # 盈亏计算
    if direction != "FLAT" and entry_price > 0 and abs(entry_price - sl_price) > 0:
        contracts_count = position_notional / entry_price
        price_diff_tp = abs(tp1_price - entry_price)
        price_diff_sl = abs(entry_price - sl_price)
        
        gross_profit = price_diff_tp * contracts_count
        gross_loss = price_diff_sl * contracts_count
        
        total_fee = (position_notional * futures_fee_rate) + ((position_notional + gross_profit) * futures_fee_rate)
        net_profit = gross_profit - total_fee
        max_loss = gross_loss + total_fee
        roe_pct = (net_profit / capital) * 100
    else:
        contracts_count, total_fee, net_profit, max_loss, roe_pct = 0, 0, 0, 0, 0

    # UI 渲染
    price_cls = "okx-price-value" if price_change_pct >= 0 else "okx-price-value okx-price-down"
    sign_str = "+" if price_change_pct >= 0 else ""
    bj_time_str = df['timestamp'].iloc[-1].strftime('%H:%M:%S')
    
    st.markdown(f"""
    <div class="okx-price-card">
        <div class="okx-price-title">
            <span><b>{selected_category.split(' ')[0]} {real_symbol}</b> ({timeframe})</span>
            <span class="time-badge">北京时间 {bj_time_str}</span>
        </div>
        <div class="{price_cls}">${curr_price:,.4f} <span style="font-size:0.9rem;">({sign_str}{price_change_pct:.2f}%)</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-card"><div class="metric-label">交易方向 ({leverage}x)</div><div class="metric-val" style="color:{action_color};">{status_text}</div></div>
        <div class="metric-card"><div class="metric-label">参考入场价</div><div class="metric-val" style="color:#38bdf8;">${entry_price:,.4f}</div></div>
        <div class="metric-card"><div class="metric-label">结构止损 (SL)</div><div class="metric-val" style="color:#f6465d;">${sl_price:,.4f}</div></div>
        <div class="metric-card"><div class="metric-label">目标止盈 (TP1)</div><div class="metric-val" style="color:#0ecb81;">${tp1_price:,.4f}</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="futures-card" style="border-left-color: {action_color};">
        <div class="futures-title" style="color: {action_color};">⚡ 头寸推演 ({leverage}x)</div>
        <div>• <b>结构高低点</b>：前高 <b>${recent_high:,.4f}</b> | 前低 <b>${recent_low:,.4f}</b></div>
        <div>• <b>开仓名义价值</b>：<b>${position_notional:.2f} USDT</b>（本金 ${capital}U × {leverage} 倍）</div>
        <div>• <b>预估爆仓价格</b>：<span style="color:#eab308; font-weight:bold;">${liq_price:,.4f}</span></div>
        <div>• <b>预计净止盈收益</b>：<span style="color:#0ecb81; font-weight:bold;">+${net_profit:.2f} USDT</span>（ROE: <b>+{roe_pct:.1f}%</b>）</div>
        <div>• <b>预计最大止损亏损</b>：<span style="color:#f6465d; font-weight:bold;">-${max_loss:.2f} USDT</span></div>
        <div style="margin-top:6px; font-size:0.78rem; color:#848e9c;">💡 <b>分析指引</b>：{advice_msg}</div>
    </div>
    """, unsafe_allow_html=True)

    # K线图表
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="K线",
                                 increasing_line_color='#0ecb81', decreasing_line_color='#f6465d',
                                 increasing_fillcolor='#0ecb81', decreasing_fillcolor='#f6465d'), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA7'], mode='lines', name='EMA7', line=dict(color='#f0b90b', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA20'], mode='lines', name='EMA20', line=dict(color='#38bdf8', width=1.2)), row=1, col=1)

    if direction != "FLAT":
        fig.add_hline(y=sl_price, line_dash="solid", line_color="#f6465d", annotation_text="结构止损 SL", annotation_position="top left", row=1, col=1)
        fig.add_hline(y=tp1_price, line_dash="dot", line_color="#0ecb81", annotation_text="目标止盈 TP", annotation_position="bottom left", row=1, col=1)

    colors = ['#0ecb81' if row['close'] >= row['open'] else '#f6465d' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df['timestamp'], y=df['volume'], name="成交量", marker_color=colors), row=2, col=1)

    fig.update_layout(xaxis_rangeslider_visible=False, height=350, paper_bgcolor='#0b0e11', plot_bgcolor='#11151c',
                      font=dict(color='#848e9c', size=10), margin=dict(l=0, r=0, t=5, b=5), showlegend=False, dragmode='zoom',
                      xaxis=dict(gridcolor='#1e2329', tickformat='%m-%d %H:%M', fixedrange=False),
                      yaxis=dict(gridcolor='#1e2329', side='right', fixedrange=False), yaxis2=dict(gridcolor='#1e2329', side='right', fixedrange=True))
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})

    if st.button("🔄 强制刷新行情"):
        st.cache_data.clear()
        st.rerun()

else:
    st.warning(f"⚠️ 暂未获取到 {symbol} 的实时行情。请确认代码是否正确或点击下方的重新连接。")
    if st.button("🔄 重新尝试连接"):
        st.cache_data.clear()
        st.rerun()