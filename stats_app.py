"""
PTCG 進階統計分析儀表板 — Streamlit App

Launch:  python -m src.main stats
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ── Page Config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="PTCG 統計分析",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Data & Translation ───────────────────────────────────────────────
DATA_DIR = Path("data")


@st.cache_data(ttl=300)
def load_data() -> dict | None:
    """Load cached tournament data."""
    path = DATA_DIR / "scraped_data.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _init_translate():
    """Return archetype → Chinese translation function."""
    try:
        from src.translation import translate_archetype
        return translate_archetype
    except ImportError:
        return lambda x: x


data = load_data()
if data is None:
    st.error("❌ 找不到資料！請先執行 `python -m src.main scrape` 抓取資料。")
    st.stop()

zh = _init_translate()

from src.analyzer.statistics import StatisticalAnalyzer  # noqa: E402

analyzer = StatisticalAnalyzer(data)

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.title("📐 統計分析")
st.sidebar.markdown("---")

min_entries = st.sidebar.slider("最低樣本數", 3, 20, 5, help="低於此數量的牌組將被排除")

SECTIONS = [
    "📊 總覽",
    "🎯 貝氏勝率",
    "📈 環境穩定性",
    "🔄 Meta 漂移偵測",
    "🏛️ 集中度分析",
    "💰 期望值 (EV)",
    "⚔️ 匹配顯著性",
]
section = st.sidebar.radio("分析項目", SECTIONS)

st.sidebar.markdown("---")
st.sidebar.caption(
    "所有統計方法均使用科學級演算法，"
    "包含正確的信賴/可信區間、假設檢定與校正。"
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_df(rows: list[dict[str, Any]], *, name_col: str = "name") -> pd.DataFrame:
    """Build a DataFrame and add a translated name column."""
    df = pd.DataFrame(rows)
    if name_col in df.columns:
        df.insert(0, "牌組", df[name_col].map(zh))
    return df


def _show_empty() -> None:
    st.warning("沒有足夠資料（請調低最低樣本數或確認資料已抓取）")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Sections
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if section == "📊 總覽":
    st.title("📊 統計分析總覽")

    col_left, col_right = st.columns(2)

    # ── Concentration snapshot ──
    with col_left:
        st.subheader("🏛️ 環境集中度")
        conc = analyzer.concentration_indices()
        if "error" not in conc:
            c1, c2, c3 = st.columns(3)
            c1.metric("Simpson's", conc["simpsons_index"],
                       help="1 = 完全多元, 0 = 完全集中")
            c2.metric("Shannon", conc["shannon_entropy"],
                       help="資訊熵，越高越多元")
            c3.metric("HHI", conc["hhi"],
                       help="< 0.15 = 競爭性環境")
            st.caption(
                f"有效物種數 {conc['effective_species']} · "
                f"均勻度 {conc['evenness']} · "
                f"牌組種類 {conc['species_richness']}"
            )
        else:
            st.info("集中度資料不足")

    # ── Meta shift snapshot ──
    with col_right:
        st.subheader("🔄 環境變化偵測")
        shift = analyzer.meta_shift_test()
        if shift["result"] == "complete":
            st.metric(
                f"{shift['previous_week']} → {shift['current_week']}",
                shift["interpretation"],
            )
            st.caption(
                f"χ² = {shift['chi_square']} · "
                f"df = {shift['degrees_of_freedom']} · "
                f"p = {shift['p_value']}"
            )
        else:
            st.info(shift.get("message", "資料不足"))

    st.markdown("---")

    # ── Top Bayesian win rates ──
    st.subheader("🎯 貝氏勝率 Top 10")
    bayes = analyzer.bayesian_win_rates(min_entries)[:10]
    if bayes:
        df = _make_df(bayes)
        st.dataframe(
            df[["牌組", "posterior_mean", "ci_low", "ci_high", "sample_size"]]
            .rename(columns={
                "posterior_mean": "貝氏勝率 %",
                "ci_low": "95% CI 下限",
                "ci_high": "95% CI 上限",
                "sample_size": "樣本數",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        _show_empty()

    # ── Top EV ──
    st.subheader("💰 期望值 Top 10")
    ev = analyzer.ev_analysis(min_entries)[:10]
    if ev:
        df = _make_df(ev)
        st.dataframe(
            df[["牌組", "ev", "std", "sharpe", "deck_count"]]
            .rename(columns={
                "ev": "EV (pts)",
                "std": "Std Dev",
                "sharpe": "Sharpe",
                "deck_count": "樣本數",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        _show_empty()


elif section == "🎯 貝氏勝率":
    st.title("🎯 貝氏勝率估計 (Beta-Binomial)")

    st.info(
        "**方法**：使用 Beta(2, 2) 弱資訊先驗，結合觀測資料計算後驗分佈。\n\n"
        "**優點**：小樣本時不會產生極端估計（如 0 % 或 100 %），"
        "可信區間寬度如實反映資料的不確定性。"
    )

    results = analyzer.bayesian_win_rates(min_entries)
    if not results:
        _show_empty()
        st.stop()

    df = _make_df(results)

    # ── Chart ──
    st.subheader("95 % 可信區間（前 20 名）")
    top = df.head(20).sort_values("posterior_mean")
    st.bar_chart(top.set_index("牌組")[["posterior_mean"]], use_container_width=True)

    # ── Full table ──
    st.subheader("完整資料")
    st.dataframe(
        df[["牌組", "observed_win_rate", "posterior_mean",
            "ci_low", "ci_high", "ci_width", "wins", "sample_size"]]
        .rename(columns={
            "observed_win_rate": "觀測勝率 %",
            "posterior_mean": "貝氏勝率 %",
            "ci_low": "CI 下限",
            "ci_high": "CI 上限",
            "ci_width": "CI 寬度",
            "wins": "優勝次數",
            "sample_size": "樣本數",
        }),
        use_container_width=True, hide_index=True,
    )

    st.caption(
        "CI 寬度越小 ＝ 估計越精確（樣本越多）。"
        "貝氏勝率向先驗均值收縮，防止小樣本偏差。"
    )


elif section == "📈 環境穩定性":
    st.title("📈 環境穩定性分析 (Coefficient of Variation)")

    st.info(
        "**CV（變異係數）**＝ 標準差 / 平均值 × 100 %\n\n"
        "低 CV → 穩定出現在環境中；高 CV → 使用率大幅波動。"
    )

    results = analyzer.meta_stability(min_entries)
    if not results:
        st.warning("需要至少兩週的資料")
        st.stop()

    df = _make_df(results)

    # ── Scatter ──
    st.subheader("穩定性 vs 使用率")
    scatter = df[["牌組", "cv", "mean_share", "deck_count"]].copy()
    scatter.columns = ["牌組", "CV (%)", "平均使用率 (%)", "總套數"]
    st.scatter_chart(scatter, x="平均使用率 (%)", y="CV (%)", size="總套數",
                     use_container_width=True)

    # ── Table ──
    st.subheader("完整資料")
    st.dataframe(
        df[["牌組", "mean_share", "std_share", "cv", "stability_label", "deck_count"]]
        .rename(columns={
            "mean_share": "平均使用率 %",
            "std_share": "標準差",
            "cv": "CV %",
            "stability_label": "穩定性",
            "deck_count": "總套數",
        }),
        use_container_width=True, hide_index=True,
    )


elif section == "🔄 Meta 漂移偵測":
    st.title("🔄 Meta 漂移偵測 (Chi-Square Test)")

    st.info(
        "**卡方適合度檢定**：比較本週與上週的牌組分佈。\n\n"
        "H₀：兩週分佈相同。若 p < 0.05 則拒絕 H₀，表示環境有顯著變化。"
    )

    result = analyzer.meta_shift_test()
    if result["result"] != "complete":
        st.warning(result.get("message", "資料不足"))
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("χ² 統計量", result["chi_square"])
    c2.metric("自由度", result["degrees_of_freedom"])
    c3.metric("p-value", result["p_value"])
    c4.metric("判定", result["interpretation"])

    st.subheader("變化最大的牌組")
    if result["top_shifts"]:
        sdf = pd.DataFrame(result["top_shifts"])
        sdf.insert(0, "牌組", sdf["archetype"].map(zh))
        st.dataframe(
            sdf[["牌組", "observed", "expected", "contribution", "direction"]]
            .rename(columns={
                "observed": "本週數量",
                "expected": "預期數量",
                "contribution": "χ² 貢獻",
                "direction": "方向",
            }),
            use_container_width=True, hide_index=True,
        )

    st.caption(
        f"本週 {result['total_current']} 套 · 上週 {result['total_previous']} 套"
    )


elif section == "🏛️ 集中度分析":
    st.title("🏛️ 環境集中度分析")

    st.info(
        "三種互補的多元化指標：\n"
        "- **Simpson's Index**：隨機抽兩個牌組屬於不同原型的機率\n"
        "- **Shannon Entropy**：資訊理論的多元化指標\n"
        "- **HHI**：赫芬達爾指數，常用於市場集中度分析"
    )

    conc = analyzer.concentration_indices()
    if "error" in conc:
        _show_empty()
        st.stop()

    # ── Core metrics ──
    st.subheader("核心指標")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Simpson's Diversity", f"{conc['simpsons_index']:.4f}")
        st.caption(f"判定：{conc['interpretation']['simpsons']}")
    with c2:
        st.metric("Shannon Entropy", f"{conc['shannon_entropy']:.4f}")
        st.caption(f"最大可能值：{conc['max_shannon']:.4f}")
    with c3:
        st.metric("HHI", f"{conc['hhi']:.4f}")
        st.caption(f"判定：{conc['interpretation']['hhi']}")

    st.markdown("---")

    # ── Detail metrics ──
    st.subheader("詳細數據")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("均勻度 (Evenness)", f"{conc['evenness']:.4f}",
              help="H / H_max — 1 = 完全均勻")
    d2.metric("有效物種數", f"{conc['effective_species']:.1f}",
              help="exp(Shannon)")
    d3.metric("第一名佔比", f"{conc['dominance_pct']} %")
    d4.metric("前三名佔比", f"{conc['top3_pct']} %")

    st.caption(
        f"均勻度判定：{conc['interpretation']['evenness']} · "
        f"前五名佔比 {conc['top5_pct']} % · "
        f"牌組種類 {conc['species_richness']} · "
        f"總套數 {conc['total_decks']}"
    )

    # ── Wilson CI ──
    st.markdown("---")
    st.subheader("📏 Wilson Score 信賴區間（Top Cut 率）")
    st.caption("比傳統 Wald 區間更準確的小樣本信賴區間")

    wilson = analyzer.wilson_ci(min_entries)
    if wilson:
        wdf = _make_df(wilson)
        st.dataframe(
            wdf[["牌組", "win_rate", "win_rate_ci_low", "win_rate_ci_high",
                 "top8_rate", "top8_rate_ci_low", "top8_rate_ci_high", "deck_count"]]
            .head(20)
            .rename(columns={
                "win_rate": "勝率 %",
                "win_rate_ci_low": "勝率 CI↓",
                "win_rate_ci_high": "勝率 CI↑",
                "top8_rate": "Top8 率 %",
                "top8_rate_ci_low": "Top8 CI↓",
                "top8_rate_ci_high": "Top8 CI↑",
                "deck_count": "樣本數",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        _show_empty()


elif section == "💰 期望值 (EV)":
    st.title("💰 期望值分析 (Expected Value)")

    st.info(
        "**EV** ＝ 每次參賽的平均預期積分\n\n"
        "積分：優勝 = 100、Top4 = 50、Top8 = 25、其他 = 0\n\n"
        "**Sharpe Ratio** ＝ EV / σ — 衡量「報酬 / 風險」比，越高越好。"
    )

    results = analyzer.ev_analysis(min_entries)
    if not results:
        _show_empty()
        st.stop()

    df = _make_df(results)

    # ── Bar chart ──
    st.subheader("EV 排名（前 20 名）")
    top = df.head(20).sort_values("ev")
    st.bar_chart(top.set_index("牌組")[["ev"]], use_container_width=True)

    # ── Risk-Reward scatter ──
    st.subheader("風險—報酬散佈圖")
    scatter = df[["牌組", "ev", "std", "deck_count"]].head(30).copy()
    scatter.columns = ["牌組", "EV", "Std Dev", "樣本數"]
    st.scatter_chart(scatter, x="Std Dev", y="EV", size="樣本數",
                     use_container_width=True)

    # ── Full table ──
    st.subheader("完整資料")
    st.dataframe(
        df[["牌組", "ev", "std", "sharpe", "ev_label",
            "wins", "top4", "top8", "deck_count"]]
        .rename(columns={
            "ev": "EV",
            "std": "Std Dev",
            "sharpe": "Sharpe",
            "ev_label": "等級",
            "wins": "優勝",
            "top4": "Top4",
            "top8": "Top8",
            "deck_count": "總套數",
        }),
        use_container_width=True, hide_index=True,
    )


elif section == "⚔️ 匹配顯著性":
    st.title("⚔️ 匹配顯著性檢定 (Binomial Exact Test)")

    st.info(
        "**雙尾精確二項檢定**：檢驗觀測到的對戰勝率是否顯著偏離 50 %。\n\n"
        "- ★ p < 0.01（高度顯著）\n"
        "- ☆ p < 0.05（顯著）\n"
        "- — 不顯著（可能只是隨機偏差）"
    )

    result = analyzer.matchup_significance()
    pairs = result.get("pairs", [])

    if not pairs:
        _show_empty()
        st.stop()

    # ── Summary metric ──
    sig_count = sum(1 for p in pairs if p["significant"])
    st.metric("顯著匹配數", f"{sig_count} / {len(pairs)}", help="p < 0.05")

    # ── Filter toggle ──
    show_only_sig = st.checkbox("只顯示顯著結果", value=True)
    visible = [p for p in pairs if p["significant"]] if show_only_sig else pairs

    if visible:
        df = pd.DataFrame(visible)
        df["對戰組合"] = df["archetype1"].map(zh) + " vs " + df["archetype2"].map(zh)
        st.dataframe(
            df[["對戰組合", "a1_wins", "a2_wins", "total", "win_rate", "p_value", "label"]]
            .rename(columns={
                "a1_wins": "A 勝",
                "a2_wins": "B 勝",
                "total": "總場次",
                "win_rate": "A 勝率 %",
                "p_value": "p-value",
                "label": "顯著性",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("沒有符合條件的結果")

    st.caption(f"檢定方法：{result['test']} · α = {result['threshold']}")
