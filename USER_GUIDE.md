# PTCG City League 牌組分析系統 - 完整使用指南

這是一份針對 **PTCG Deck Analyze** 專案的詳細使用指南。本系統協助玩家從日本 City League 賽事數據中，分析當前的環境圖譜（Meta Game）、牌組構築趨勢與對戰優劣勢。

---

## 📚 目錄

1. [系統概覽](#1-系統概覽)
2. [安裝與設定](#2-安裝與設定)
3. [快速上手 (Quick Start)](#3-快速上手-quick-start)
4. [核心指標說明](#4-核心指標說明)
5. [CLI 指令詳解](#5-cli-指令詳解)
6. [網頁介面功能](#6-網頁介面功能)
7. [常見問題 (FAQ)](#7-常見問題-faq)

---

## 1. 系統概覽

本系統主要包含三個核心模組：
- **爬蟲 (Scraper)**：從 Limitless TCG 抓取日本 City League 的比賽結果與牌組列表。
- **分析器 (Analyzer)**：計算牌型分布、勝率分數、卡片使用率與對戰優劣矩陣。
- **Web 介面**：提供互動式的圖表與資料視覺化呈現，並支援繁體中文卡牌顯示。

---

## 2. 安裝與設定

在使用本系統前，請確保您的環境滿足以下需求：
- **OS**: Windows / macOS / Linux
- **Python**: 3.11 或以上版本
- **套件管理器**: 建議使用 [uv](https://docs.astral.sh/uv/) (效能更佳)，亦可使用標準 pip。

### 安裝步驟

1.  **複製專案代碼**
    ```bash
    git clone <repository_url>
    cd PTCG_deck_analyze
    ```

2.  **安裝依賴套件**
    使用 `uv` 自動建立虛擬環境並安裝套件：
    ```bash
    uv sync
    ```

---

## 3. 快速上手 (Quick Start)

最簡單的使用方式是透過 `workflow` 指令，它會自動完成資料更新的所有步驟。

### 第一步：執行完整工作流程
這會同步中文卡牌資料庫、爬取最近 14 天的賽事、並建立卡片映射。
```bash
uv run python -m src.main workflow
```
*初次執行可能需要 5-10 分鐘，請耐心等待。*

### 第二步：啟動網頁介面
資料準備好後，啟動 Web Server 查看分析結果。
```bash
uv run python -m src.main web
```
打開瀏覽器訪問：**http://127.0.0.1:5000**

---

## 4. 核心指標說明

在分析報告中，您會看到幾個關鍵指標，其定義如下：

### 🏆 勝率分數 (Win Rate Score)
**注意**：這不是單純的「勝場/總場數」，而是一個**加權表現分數**，更能反映牌組在賽事中的宰制力。

計算公式為：
- **獲得冠軍 (1st)**：獲得 6 分 (Top8 + Top4 + Win)
- **進入四強 (Top 4)**：獲得 3 分 (Top8 + Top4)
- **進入八強 (Top 8)**：獲得 1 分
- **八強以外**：0 分

$$ \text{Win Rate \%} = \frac{\text{總得分}}{\text{總參賽數} \times 6} \times 100\% $$

- **100%**：代表該牌型參加的每一場比賽都拿下了冠軍。
- **50%**：代表平均表現約為四強等級。
- **16.7%**：代表平均表現約為八強等級。

### 📊 使用率 (Usage Rate)
該牌型在選定時間範圍內的所有參賽牌組中所佔的比例。
$$ \text{Usage Rate} = \frac{\text{該牌型參賽數}}{\text{總參賽數}} $$

### 🔝 Top 8 入圍率
該牌型進入八強的機率。高入圍率通常代表該牌組穩定性高。

---

## 5. CLI 指令詳解

所有指令皆透過 `src.main` 入口執行。

### `workflow` - 自動化流程
整合了卡牌同步、爬蟲與映射的複合指令。
- `--days N`：指定爬取過去 N 天的資料 (預設 14)。
- `--skip-cards`：跳過卡牌資料庫同步 (除了第一次執行外，通常可以加上此參數以節省時間)。

```bash
# 日常更新 (最近 7 天，不重新下載卡牌庫)
uv run python -m src.main workflow --days 7 --skip-cards
```

### `scrape` - 資料爬取
手動控制爬蟲行為。
- `--limit N`：限制爬取的賽事數量。
- `--days N`：限制爬取的天數範圍。
- `--fetch-cards`：**重要**。是否抓取每副牌的詳細卡表。若不加此參數，將無法進行單卡分析 (如核心卡/Tech卡分析)。
- `--update-card-map`：更新 Limitless 英文卡名與中文資料庫的對照表。

```bash
# 深度爬取：最近 30 天，包含詳細卡表 (速度較慢但資料最完整)
uv run python -m src.main scrape --days 30 --fetch-cards
```

### `analyze` - 文字版分析
在終端機直接查看分析摘要。
- `--archetype "Name"`：查看特定牌型的詳細數據 (需使用英文名稱，如 "Dragapult")。

```bash
# 查看多龍巴魯托 (Dragapult) 的詳細數據
uv run python -m src.main analyze --archetype "dragapult"
```

### `web` - 網頁伺服器
- `--port N`：指定連接埠 (預設 5000)。
- `--debug`：開啟除錯模式。

---

## 6. 網頁介面功能

網頁版提供了最豐富的視覺化分析功能。

### 🏠 儀表板 (Dashboard)
- **環境概覽**：顯示目前的總賽事數、牌組數與牌型種類。
- **勝率排行 (Bar Chart)**：長條圖顯示各牌型的「勝率分數」。
- **牌型分布 (Doughnut Chart)**：圓餅圖顯示環境中的牌組佔比 (Meta Share)。
- **趨勢變化 (Line Chart)**：折線圖追蹤各牌型在過去幾週的使用率消長。

### ⚔️ 對戰優劣勢熱力圖 (Matchup Heatmap)
這是一個矩陣圖表，紅綠色階顯示優劣勢：
- **綠色**：優勢對局 (勝率 > 55%)
- **紅色**：劣勢對局 (勝率 < 45%)
- **透明/灰色**：均勢或資料不足

### 🔍 牌型詳情 (Archetype Detail)
點擊任一牌型（或在列表中選擇），會開啟詳細視窗：
1. **基礎數據**：參賽數、勝率、Top 8 率。
2. **ACE SPEC 使用率**：統計該牌型最常使用的 ACE SPEC 卡片。
3. **核心卡片 (Core Cards)**：幾乎每副牌都會放的卡片 (>80% 使用率)。
4. **選配卡片 (Tech Cards)**：玩家根據環境調整的卡片 (20% - 80% 使用率)。
5. **近期上位構築**：列出最近取得好成績的牌表連結。

### 🔧 進階：卡牌資料庫管理
如果您需要除錯或查詢本地卡牌資料庫，可以使用 `cards` 指令 (此指令會透傳參數給 `ptcg_tw` 工具)。

```bash
# 查詢卡片 (模糊搜尋)
uv run python -m src.main cards query --name "噴火龍"

# 顯示特定卡片詳情
uv run python -m src.main cards show --card-id 12345

# 手動同步繁中卡牌 (指定 H, I, J 標記)
uv run python -m src.main cards sync --regulation-mark H,I,J
```

---

## 7. 常見問題 (FAQ)

**Q: 為什麼「勝率」看起來很低 (例如只有 30%)？**
A: 請參考 [核心指標說明](#4-核心指標說明)。本系統的勝率是「積分制」，30% 其實是非常優秀的數據，代表平均表現介於八強到四強之間。一般來說，超過 20% 即屬於強勢牌組。

**Q: 為什麼某些卡片顯示 "Unknown" 或沒有中文圖片？**
A: 這通常是因為新卡片尚未建立映射，或是 Limitless 使用了不同的英文名稱。
1. 首先嘗試更新映射表：
   ```bash
   uv run python -m src.main scrape --update-card-map
   ```
2. 如果還是不行，可能是中文資料庫尚未有該卡片資料 (例如新擴充包剛出)。您可以嘗試手動同步：
   ```bash
   uv run python -m src.main cards sync --regulation-mark H,I,J
   ```

**Q: 爬蟲執行出現大量錯誤或是 429 Too Many Requests？**
A: Limitless TCG 可能會對過於頻繁的請求進行阻擋。
- 預設爬蟲已有 1 秒延遲。您可以嘗試增加延遲時間：
  ```bash
  uv run python -m src.main scrape --delay 3.0
  ```
- 或是減少 `--workers` 數量 (若使用 `cards sync` 時)。

**Q: 網頁介面無法開啟？**
A: 請確認 Port 5000 是否被佔用。您可以指定其他 Port：
```bash
uv run python -m src.main web --port 8080
```
