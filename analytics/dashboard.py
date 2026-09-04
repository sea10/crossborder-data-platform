"""经营分析大屏（③ 分析层）

用法: 在项目根目录执行  streamlit run analytics/dashboard.py

可视化设计规范（面试可讲）:
- KPI 用数字卡片（hero number），趋势用单序列折线——禁止双轴图（两个量两个图）
- 品类颜色固定映射：颜色跟随实体（品类），不随排序/筛选变化
- 状态色（红/黄告警）只用于异常提醒，绝不拿来做图例色
- 图表配色来自经过色盲安全验证的固定色板
"""
import altair as alt
import streamlit as st

from database import metrics as m

st.set_page_config(page_title="跨境电商经营大屏", page_icon="📊", layout="wide")

# 分类色板（固定顺序，不循环；5 个品类各占一席）
CAT_COLORS = {
    "Electronics": "#2a78d6",  # blue
    "Sports": "#eb6834",       # orange
    "Beauty": "#1baf7a",       # aqua
    "Home": "#eda100",         # yellow
    "Kitchen": "#e87ba4",      # magenta
}
GRID_COLOR = "#e1e0d9"

# 异常阈值（与 report_pusher 一致）
CANCEL_RATE_THRESHOLD = 8.0
GMV_DROP_THRESHOLD = -10.0


@st.cache_data(ttl=300, show_spinner=False)
def get_orders():
    return m.load_orders()


@st.cache_data(ttl=300, show_spinner=False)
def get_snapshots():
    return m.load_snapshots()


def kpi_row(orders):
    c = st.columns(6)
    c[0].metric("GMV（已发货）", f"${m.gmv(orders):,.0f}")
    c[1].metric("订单数", f"{m.order_count(orders):,}")
    c[2].metric("客单价 AOV", f"${m.aov(orders)}")
    c[3].metric("取消率", f"{m.cancellation_rate(orders)}%")
    c[4].metric("复购SKU占比", f"{m.repeat_purchase_sku_ratio(orders)}%")
    c[5].metric("TOP10 集中度", f"{m.top_sku_concentration(orders)}%")


def render_shop_tab(orders):
    kpi_row(orders)

    # 异常告警：状态色只出现在这里
    cancel = m.cancellation_rate(orders)
    if cancel > CANCEL_RATE_THRESHOLD:
        st.error(f"⚠️ 取消率 {cancel}% 超过 {CANCEL_RATE_THRESHOLD}% 阈值，建议排查库存与物流环节")
    trend = m.monthly_trend(orders)
    full_months = trend.iloc[:-1]  # 最后一个自然月不完整，环比取完整月
    if len(full_months) >= 2 and full_months.iloc[-1]["GMV环比%"] < GMV_DROP_THRESHOLD:
        st.warning(f"⚠️ 上月 GMV 环比 {full_months.iloc[-1]['GMV环比%']}%，下滑超阈值，建议关注流量与转化")

    st.divider()
    st.subheader("📈 月度经营趋势（近 6 个月）")
    t = trend.tail(6).copy()
    c1, c2 = st.columns(2)  # 单轴原则：GMV 与订单数量级不同，分成两张图
    c1.caption("GMV（美元）")
    c1.line_chart(t.set_index("month")["GMV"], color=CAT_COLORS["Electronics"], height=280)
    c2.caption("订单数")
    c2.line_chart(t.set_index("month")["订单数"], color=CAT_COLORS["Sports"], height=280)

    st.subheader("🏷️ 品类销售结构")
    cat = m.category_breakdown(orders)
    bar = (
        alt.Chart(cat)
        .mark_bar(size=28, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("GMV:Q", axis=alt.Axis(gridColor=GRID_COLOR)),
            y=alt.Y("category:N", sort="-x", title=None),
            color=alt.Color(
                "category:N",
                scale=alt.Scale(domain=list(CAT_COLORS), range=list(CAT_COLORS.values())),
                legend=None,  # y 轴品类名已承载身份，颜色不作为唯一识别
            ),
            tooltip=["category", "GMV", "订单数", "GMV占比%"],
        )
        .properties(height=240)
    )
    st.altair_chart(bar)

    c3, c4 = st.columns(2)
    c3.subheader("💰 价格带分布（订单占比 %）")
    price = m.price_band_distribution(orders)
    c3.bar_chart(price.set_index("price_band")["订单占比%"], color=CAT_COLORS["Beauty"], height=240)
    c4.subheader("📅 一周订单分布（日均）")
    weekday = m.weekday_analysis(orders)
    c4.bar_chart(weekday.set_index("星期(0=周一)")["日均订单"], color=CAT_COLORS["Kitchen"], height=240)


def render_market_tab(snaps):
    st.subheader("💵 各品类榜单价格")
    st.dataframe(m.market_price_stats(snaps), width="stretch")
    st.subheader("⭐ 各品类评分")
    st.dataframe(m.market_rating_stats(snaps), width="stretch")

    c1, c2 = st.columns(2)
    c1.subheader("🔥 热门商品 TOP10（评论数=需求热度）")
    c1.dataframe(m.hot_products(snaps), width="stretch", height=400)
    c2.subheader("🥊 类目竞争度")
    c2.dataframe(m.category_competitiveness(snaps), width="stretch")
    c2.subheader("📉 价格带-需求关系")
    c2.dataframe(m.price_review_relationship(snaps), width="stretch")

    st.subheader("📊 榜单动态（最近两批采集对比）")
    rc = m.rank_changes(snap=snaps)
    if rc:
        risers, fallers = rc
        r1, r2 = st.columns(2)
        r1.caption("排名上升 TOP5")
        r1.dataframe(risers, width="stretch")
        r2.caption("排名下降 TOP5")
        r2.dataframe(fallers, width="stretch")
    else:
        st.info("当前只有一批采集数据。明天再跑一次采集后，这里会展示真实排名变化。")


orders = get_orders()
snaps = get_snapshots()

st.title("🛒 跨境电商经营数据中台")
st.caption(
    f"订单数据截至 {orders['order_date'].max():%Y-%m-%d} ｜ "
    f"榜单快照截至 {snaps['captured_at'].max():%Y-%m-%d %H:%M} ｜ "
    f"采集批次 {snaps['captured_at'].nunique()} 批"
)
if st.button("🔄 刷新数据"):
    st.cache_data.clear()
    st.rerun()

tab_shop, tab_market = st.tabs(["🏪 店铺经营", "🌍 市场与竞品"])
with tab_shop:
    render_shop_tab(orders)
with tab_market:
    render_market_tab(snaps)
