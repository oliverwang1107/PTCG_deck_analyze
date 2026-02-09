# PTCG 繁中卡牌本地資料庫 (SQLite)

這個專案會從官方卡牌搜尋網站抓取卡片資料（繁中），解析後寫入本機 `SQLite`，並提供簡單的本地瀏覽介面。

資料來源：
- `https://asia.pokemon-card.com/tw/card-search/list/`
- `https://asia.pokemon-card.com/tw/card-search/detail/<id>/`

## 使用 uv（推薦）

`uv` 會自動建立 `.venv`、安裝依賴、並把本專案安裝成可執行指令 `ptcg_tw`。

```bash
uv run ptcg_tw --help
```

範例：只抓第 1 頁、最多 10 張（測試用）

```bash
uv run ptcg_tw sync --db ptcg_tw.sqlite --start-page 1 --end-page 1 --limit 10
```

只抓卡標為 `G/H/I` 的卡片（建議新開一個 DB）：

```bash
uv run ptcg_tw sync --db ptcg_ghi.sqlite --regulation-mark G,H,I
```

列出單張卡片詳細資料（終端機輸出）：

```bash
uv run ptcg_tw show --db ptcg_tw.sqlite --card-id 14661
```

將所有招式/特性文字正規化並拆成指令（寫回 DB 的 `effect_text_norm`、`instructions_json`）：

```bash
uv run ptcg_tw normalize-effects --db ptcg_tw.sqlite
```

用 OpenRouter/LLM 拆成更結構化指令（寫回 `instructions_json`）：

```bash
setx OPENROUTER_API_KEY "你的API鍵"  # Windows 一次設定（或用 .env）
uv run ptcg_tw llm-effects --db ptcg_tw.sqlite --model anthropic/claude-3.5-sonnet --limit 20
```

也可用 `.env` 存放憑證（專案根目錄建立 `.env`）：
```
OPENROUTER_API_KEY=你的API鍵
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions
```

啟動本地瀏覽介面：

```bash
uv run ptcg_tw serve --db ptcg_tw.sqlite --host 127.0.0.1 --port 8000
```

然後開 `http://127.0.0.1:8000/`。

### 瀏覽介面功能

- 列表頁：搜尋卡名、用下拉選單過濾 `類型 / 卡標 / 系列`，支援分頁與排序。
- 詳情頁：上一張/下一張導覽（會沿用你在列表頁的篩選條件），點卡圖可放大，並可展開 `Raw JSON` 方便檢查解析結果。

### 也可以手動啟用 venv（可選）

第一次 `uv run ...` 之後會有 `.venv`，你也可以改用「啟用後直接跑」：

```powershell
.\.venv\Scripts\Activate.ps1
ptcg_tw sync --db ptcg_tw.sqlite --start-page 1 --end-page 1 --limit 10
```

## 不用 uv（備用）

安裝依賴：

```bash
python -m pip install -r requirements.txt
```

用 module 方式執行（不需要安裝成指令）：

```bash
python -m ptcg_tw sync --db ptcg_tw.sqlite --start-page 1 --end-page 1 --limit 10
```

## 參數提示

- `sync --skip-existing` 預設為 `true`，所以可以安全重跑，用來續抓或補漏。
- `sync --delay` 是「全域」請求間隔（秒），建議不要設太小，避免對站點造成壓力。
- `sync --card-type` 支援：`all | pokemon | trainer | energy`（會透過 list 的 POST 先設定搜尋條件，再翻頁抓取）。
- `sync --regulation-mark` 會在抓到 detail 後，以卡片頁面上的規則標記（例：`G`、`H`、`I`）做過濾，只把符合者寫入 DB。

## DB 結構（簡述）

- `cards`：一張卡一列（含 `raw_json` 保存完整解析結果）
- `skills`：招式/特性/效果等（依 `idx` 排序，`kind` 會是頁面上的區塊標題，例如「招式」、「特性」、「物品卡」等）

你可以直接用任何 SQLite 工具打開 `ptcg_tw.sqlite` 做查詢或匯出。

## 注意事項

- 請遵守官方網站的使用條款與合理抓取頻率；建議使用 `--delay` 做節流。
- 本專案的資料解析依賴目前頁面 HTML 結構；若官方改版，可能需要調整解析邏輯（`ptcg_tw/scraper.py`）。
