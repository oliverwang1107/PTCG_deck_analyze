from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency, but listed in requirements
    load_dotenv = None

from . import db as dbmod
from .db import copy_cards_from_db
from .effects import normalize_text, split_into_instructions
from .llm import call_openrouter_effects
from .scraper import (
    RateLimiter,
    SearchParams,
    build_session,
    extract_card_ids_from_list_html,
    fetch_detail_html,
    fetch_list_page,
    parse_card_detail_html,
    start_search,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

if load_dotenv:
    load_dotenv()

@dataclass(frozen=True)
class FetchResult:
    card_id: int
    card: dict[str, Any] | None = None
    skills: list[dbmod.Skill] | None = None
    error: str | None = None


_tls = threading.local()


def _get_thread_session():
    s = getattr(_tls, "session", None)
    if s is None:
        s = build_session()
        _tls.session = s
    return s


def cmd_init_db(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = dbmod.connect(db_path)
    dbmod.init_db(conn)
    print(f"DB initialized: {db_path}")
    return 0


def cmd_copy_cards(args: argparse.Namespace) -> int:
    """Copy cards from source DB to destination DB by regulation mark."""
    src_path = Path(args.src)
    dst_path = Path(args.dst)
    
    if not src_path.exists():
        print(f"source DB not found: {src_path}", file=sys.stderr)
        return 1
    
    # Parse regulation marks
    marks: set[str] = set()
    if args.regulation_mark:
        for item in args.regulation_mark:
            for part in str(item).replace(" ", ",").split(","):
                part = part.strip()
                if part:
                    marks.add(part.upper())
    
    src_conn = dbmod.connect(src_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_conn = dbmod.connect(dst_path)
    
    copied = copy_cards_from_db(src_conn, dst_conn, regulation_marks=marks or None)
    print(f"copied {copied} cards from {src_path} to {dst_path}", file=sys.stderr)
    if marks:
        print(f"regulation marks: {','.join(sorted(marks))}", file=sys.stderr)
    return 0


def _parse_card_type_arg(card_type: str) -> str:
    v = card_type.strip().lower()
    return {
        "all": "all",
        "pokemon": "1",
        "trainer": "2",
        "trainers": "2",
        "energy": "3",
    }.get(v, v)


def _fetch_list_page_task(page_no: int, limiter: RateLimiter) -> tuple[int, list[int]]:
    """Fetch a single list page and extract card IDs."""
    session = _get_thread_session()
    html = fetch_list_page(session, limiter, page_no)
    ids = extract_card_ids_from_list_html(html)
    return page_no, ids


def _discover_card_ids(
    *,
    session,
    limiter: RateLimiter,
    params: SearchParams,
    start_page: int,
    end_page: int | None,
    list_workers: int = 1,
) -> tuple[list[int], int | None]:
    html1, total_pages = start_search(session, limiter, params)
    if end_page is None and total_pages is not None:
        end_page = total_pages
    if end_page is None:
        end_page = start_page

    # Page 1 is already fetched
    page1_ids = extract_card_ids_from_list_html(html1)
    
    if list_workers <= 1 or end_page <= start_page:
        # Sequential mode (original behavior)
        ids: list[int] = list(page1_ids) if start_page == 1 else []
        first_page = 2 if start_page == 1 else start_page
        for page in range(first_page, end_page + 1):
            html = fetch_list_page(session, limiter, page)
            ids.extend(extract_card_ids_from_list_html(html))
            print(f"list page {page}/{end_page}: +{len(set(ids))} ids", file=sys.stderr)
    else:
        # Parallel mode
        ids = list(page1_ids) if start_page == 1 else []
        print(f"list page 1/{end_page}: +{len(page1_ids)} ids (parallel mode, {list_workers} workers)", file=sys.stderr)
        
        pages_to_fetch = list(range(2 if start_page == 1 else start_page, end_page + 1))
        
        with ThreadPoolExecutor(max_workers=list_workers) as ex:
            futs = [ex.submit(_fetch_list_page_task, p, limiter) for p in pages_to_fetch]
            results: dict[int, list[int]] = {}
            for fut in as_completed(futs):
                page_no, page_ids = fut.result()
                results[page_no] = page_ids
                done_count = len(results) + 1  # +1 for page 1
                print(f"list page {page_no}/{end_page}: done ({done_count}/{end_page})", file=sys.stderr)
        
        # Maintain page order when collecting IDs
        for p in sorted(results.keys()):
            ids.extend(results[p])

    # Preserve order but de-duplicate across pages
    unique: dict[int, None] = {}
    for cid in ids:
        unique[cid] = None
    return list(unique.keys()), total_pages


def _fetch_one(card_id: int, limiter: RateLimiter) -> FetchResult:
    try:
        session = _get_thread_session()
        html = fetch_detail_html(session, limiter, card_id)
        if html is None:
            return FetchResult(card_id=card_id, error="redirected_to_list")
        card, skills = parse_card_detail_html(card_id, html)
        return FetchResult(card_id=card_id, card=card, skills=skills)
    except Exception as e:  # noqa: BLE001 - CLI tool: keep going
        return FetchResult(card_id=card_id, error=str(e))


def cmd_sync(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = dbmod.connect(db_path)
    dbmod.init_db(conn)

    limiter = RateLimiter(args.delay)
    allowed_marks: set[str] | None = None
    if args.regulation_mark:
        marks: set[str] = set()
        for item in args.regulation_mark:
            for part in str(item).replace(" ", ",").split(","):
                part = part.strip()
                if part:
                    marks.add(part.upper())
        allowed_marks = marks or None

    if args.card_id is not None:
        card_ids = [int(args.card_id)]
    else:
        params = SearchParams(
            keyword=args.keyword or "",
            card_type=_parse_card_type_arg(args.card_type),
            regulation=args.regulation,
        )
        session = build_session()
        start_page = max(1, int(args.start_page))
        end_page = int(args.end_page) if args.end_page is not None else None
        card_ids, total_pages = _discover_card_ids(
            session=session,
            limiter=limiter,
            params=params,
            start_page=start_page,
            end_page=end_page,
            list_workers=int(args.list_workers),
        )
        if total_pages is not None:
            print(f"total pages: {total_pages}", file=sys.stderr)

    existing = dbmod.get_existing_card_ids(conn) if args.skip_existing else set()
    to_fetch = [cid for cid in card_ids if cid not in existing]
    if args.limit is not None:
        to_fetch = to_fetch[: int(args.limit)]

    print(
        f"discovered={len(card_ids)} existing={len(existing)} to_fetch={len(to_fetch)}",
        file=sys.stderr,
    )
    if not to_fetch:
        return 0

    ok = 0
    fail = 0
    skipped = 0
    with ThreadPoolExecutor(max_workers=int(args.workers)) as ex:
        futs = [ex.submit(_fetch_one, cid, limiter) for cid in to_fetch]
        for fut in as_completed(futs):
            res = fut.result()
            if res.card is None or res.skills is None:
                fail += 1
                print(f"[fail] {res.card_id}: {res.error}", file=sys.stderr)
                continue
            if allowed_marks is not None:
                mark = (res.card.get("regulation_mark") or "").strip().upper()
                if mark not in allowed_marks:
                    skipped += 1
                    continue
            dbmod.upsert_card(conn, card_id=res.card_id, card=res.card, skills=res.skills)
            ok += 1
            if ok % 50 == 0:
                print(f"[ok] {ok}/{len(to_fetch)}", file=sys.stderr)

    if allowed_marks is not None:
        print(f"done: ok={ok} skipped={skipped} fail={fail} marks={','.join(sorted(allowed_marks))} db={db_path}", file=sys.stderr)
    else:
        print(f"done: ok={ok} fail={fail} db={db_path}", file=sys.stderr)
    return 0 if fail == 0 else 2


def cmd_query(args: argparse.Namespace) -> int:
    conn = dbmod.connect(args.db)
    dbmod.init_db(conn)

    name = (args.name or "").strip()
    if not name:
        print("--name is required", file=sys.stderr)
        return 2

    limit = int(args.limit)
    cur = conn.execute(
        """
        SELECT card_id, name, expansion_code, collector_number, card_type
        FROM cards
        WHERE name LIKE ?
        ORDER BY card_id DESC
        LIMIT ?;
        """,
        (f"%{name}%", limit),
    )
    rows = cur.fetchall()
    for r in rows:
        print(
            f"{r['card_id']}\t{r['name']}\t{r['expansion_code'] or ''}\t{r['collector_number'] or ''}\t{r['card_type'] or ''}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    conn = dbmod.connect(args.db)
    dbmod.init_db(conn)

    card_id = int(args.card_id)
    card = conn.execute("SELECT * FROM cards WHERE card_id = ?;", (card_id,)).fetchone()
    if card is None:
        print(f"card not found: {card_id}", file=sys.stderr)
        return 2

    skills = conn.execute(
        """
        SELECT idx, kind, name, cost_json, damage, effect
        FROM skills
        WHERE card_id = ?
        ORDER BY idx ASC;
        """,
        (card_id,),
    ).fetchall()

    if args.json:
        payload = dict(card)
        payload["skills"] = [
            {
                "idx": int(s["idx"]),
                "kind": s["kind"],
                "name": s["name"],
                "cost": json.loads(s["cost_json"] or "[]"),
                "damage": s["damage"],
                "effect": s["effect"],
            }
            for s in skills
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    def _fmt_energy(code: str | None) -> str:
        return f"[{code}]" if code else ""

    print(f"{card['name']}  (card_id={card_id})")
    header_bits: list[str] = []
    if card["card_type"]:
        header_bits.append(str(card["card_type"]))
    if card["hp"] is not None:
        header_bits.append(f"HP {int(card['hp'])}")
    if card["element_code"] or card["element"]:
        header_bits.append(f"{_fmt_energy(card['element_code'])}{card['element'] or ''}".strip())
    if card["evolve_marker"]:
        header_bits.append(str(card["evolve_marker"]))
    if header_bits:
        print(" - " + " / ".join([b for b in header_bits if b]))

    def _line(label: str, value: Any) -> None:
        if value is None:
            return
        s = str(value).strip()
        if not s or s == "--":
            return
        print(f"{label}: {s}")

    _line("系列", f"{card['expansion_code'] or ''} {card['expansion_name'] or ''}".strip() or None)
    _line("卡號", card["collector_number"])
    _line("規則標記", card["regulation_mark"])
    _line("插畫家", card["illustrator"])
    _line("圖片", card["image_url"])
    _line("來源", card["source_url"])
    _line("抓取時間", card["fetched_at"])

    weak = None
    if card["weakness_value"] not in (None, "--"):
        weak = f"{_fmt_energy(card['weakness_code'])} {card['weakness_value']}".strip()
    _line("弱點", weak)

    resist = None
    if card["resistance_value"] not in (None, "--"):
        resist = f"{_fmt_energy(card['resistance_code'])} {card['resistance_value']}".strip()
    _line("抵抗力", resist)

    if card["retreat_cost"] is not None:
        _line("撤退", int(card["retreat_cost"]))

    if card["pokedex_no"] is not None:
        _line("No.", f"No.{int(card['pokedex_no'])}")
    _line("身高", f"{card['height_m']} m" if card["height_m"] is not None else None)
    _line("體重", f"{card['weight_kg']} kg" if card["weight_kg"] is not None else None)
    if card["description"]:
        print("說明:")
        print(str(card["description"]))

    if skills:
        print("\n招式/效果:")
        for s in skills:
            kind = (s["kind"] or "").strip()
            name = (s["name"] or "").strip()
            dmg = (s["damage"] or "").strip()
            effect = (s["effect"] or "").strip()
            try:
                cost = json.loads(s["cost_json"] or "[]")
            except Exception:
                cost = []
            cost_txt = "".join(_fmt_energy(c) for c in cost) if isinstance(cost, list) else ""
            left = " ".join([x for x in [kind, name] if x])
            right = " ".join([x for x in [cost_txt, dmg] if x])
            print(f"- {left}".rstrip())
            if right:
                print(f"  {right}")
            if effect:
                for line in effect.splitlines():
                    print(f"  {line}")

    return 0


def cmd_normalize_effects(args: argparse.Namespace) -> int:
    conn = dbmod.connect(args.db)
    dbmod.init_db(conn)

    cur = conn.execute(
        """
        SELECT skill_id, card_id, effect, effect_text_norm, instructions_json
        FROM skills
        WHERE effect IS NOT NULL;
        """
    )
    rows = cur.fetchall()
    updated = 0
    for r in rows:
        sid = int(r["skill_id"])
        effect_raw = r["effect"]
        effect_norm = normalize_text(effect_raw)
        instructions = split_into_instructions(effect_norm)
        conn.execute(
            """
            UPDATE skills
            SET effect_text_norm = ?, instructions_json = ?
            WHERE skill_id = ?;
            """,
            (effect_norm, json.dumps(instructions, ensure_ascii=False), sid),
        )
        updated += 1
    conn.commit()
    print(f"normalized skills: {updated}")
    return 0


def cmd_llm_effects(args: argparse.Namespace) -> int:
    conn = dbmod.connect(args.db)
    dbmod.init_db(conn)

    cur = conn.execute(
        """
        SELECT skill_id, card_id, name, effect, effect_text_norm, instructions_json
        FROM skills
        WHERE effect IS NOT NULL
        """
        + ("" if args.force else " AND (instructions_json IS NULL OR instructions_json = '')")
        + " LIMIT ?;",
        (args.limit,),
    )
    rows = cur.fetchall()
    if not rows:
        print("no skills to process")
        return 0

    model = args.model
    api_key = args.api_key or None
    base_url = args.base_url or None
    processed = 0
    for r in rows:
        sid = int(r["skill_id"])
        card_id = int(r["card_id"])
        text = r["effect_text_norm"] or r["effect"] or ""
        if not text.strip():
            continue
        try:
            instructions = call_openrouter_effects(
                text=text,
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=args.temperature,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[fail] card {card_id} skill {sid}: {e}", file=sys.stderr)
            continue
        conn.execute(
            """
            UPDATE skills
            SET instructions_json = ?
            WHERE skill_id = ?;
            """,
            (json.dumps(instructions, ensure_ascii=False), sid),
        )
        processed += 1
        if processed % 20 == 0:
            conn.commit()
            print(f"[ok] {processed}/{len(rows)}")
    conn.commit()
    print(f"done: {processed} skills updated (model={model})")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .serve import serve

    serve(args.db, host=args.host, port=int(args.port))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ptcg_tw", description="PTCG 繁中卡牌本地資料庫工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-db", help="建立/初始化 SQLite schema")
    p_init.add_argument("--db", default="ptcg_tw.sqlite", help="SQLite 檔案路徑")
    p_init.set_defaults(func=cmd_init_db)

    p_copy = sub.add_parser("copy-cards", help="從來源 DB 複製卡片到目標 DB（可指定卡標）")
    p_copy.add_argument("--src", required=True, help="來源 SQLite 檔案路徑")
    p_copy.add_argument("--dst", required=True, help="目標 SQLite 檔案路徑")
    p_copy.add_argument("--regulation-mark", action="append", help="只複製指定卡標（例如 H,I,J；可重複給多次）")
    p_copy.set_defaults(func=cmd_copy_cards)

    p_sync = sub.add_parser("sync", help="從官方卡牌搜尋抓資料並寫入 DB")
    p_sync.add_argument("--db", default="ptcg_tw.sqlite", help="SQLite 檔案路徑")
    p_sync.add_argument("--card-id", type=int, help="只抓單張卡（官方 detail ID）")
    p_sync.add_argument("--card-type", default="all", help="all|pokemon|trainer|energy")
    p_sync.add_argument("--regulation", default="all", help="1|2|3|all")
    p_sync.add_argument("--regulation-mark", action="append", help="只寫入指定卡標（例如 G,H,I；可重複給多次）")
    p_sync.add_argument("--keyword", default="", help="搜尋關鍵字（預設空字串）")
    p_sync.add_argument("--start-page", default=1, type=int, help="從第幾頁開始（預設 1）")
    p_sync.add_argument("--end-page", type=int, help="抓到第幾頁（預設抓到最後一頁）")
    p_sync.add_argument("--limit", type=int, help="最多抓幾張（除錯用）")
    p_sync.add_argument("--workers", default=4, type=int, help="抓詳情的並行數（預設 4）")
    p_sync.add_argument("--list-workers", default=8, type=int, help="抓列表頁的並行數（預設 8）")
    p_sync.add_argument("--delay", default=0.1, type=float, help="全域請求間隔秒數（預設 0.1）")
    p_sync.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True, help="略過已存在的 card_id（預設 true）")
    p_sync.set_defaults(func=cmd_sync)

    p_query = sub.add_parser("query", help="以卡名模糊查詢")
    p_query.add_argument("--db", default="ptcg_tw.sqlite", help="SQLite 檔案路徑")
    p_query.add_argument("--name", required=True, help="卡名片段")
    p_query.add_argument("--limit", default=20, type=int, help="最多列出幾筆（預設 20）")
    p_query.set_defaults(func=cmd_query)

    p_show = sub.add_parser("show", help="列出單張卡片詳細資料")
    p_show.add_argument("--db", default="ptcg_tw.sqlite", help="SQLite 檔案路徑")
    p_show.add_argument("--card-id", required=True, type=int, help="官方 detail ID（cards.card_id）")
    p_show.add_argument("--json", action=argparse.BooleanOptionalAction, default=False, help="輸出 JSON（預設 false）")
    p_show.set_defaults(func=cmd_show)

    p_norm = sub.add_parser("normalize-effects", help="將招式/特性文字正規化並拆成指令")
    p_norm.add_argument("--db", default="ptcg_tw.sqlite", help="SQLite 檔案路徑")
    p_norm.set_defaults(func=cmd_normalize_effects)

    p_llm = sub.add_parser("llm-effects", help="使用 OpenRouter/LLM 將招式/特性拆成指令 JSON")
    p_llm.add_argument("--db", default="ptcg_tw.sqlite", help="SQLite 檔案路徑")
    p_llm.add_argument("--model", default="anthropic/claude-3.5-sonnet", help="OpenRouter 模型名稱")
    p_llm.add_argument("--api-key", help="覆寫 OPENROUTER_API_KEY")
    p_llm.add_argument("--base-url", help="覆寫 OpenRouter API URL（預設官方）")
    p_llm.add_argument("--limit", type=int, default=50, help="最多處理幾筆（預設 50）")
    p_llm.add_argument("--temperature", type=float, default=0.1, help="溫度（預設 0.1）")
    p_llm.add_argument("--force", action=argparse.BooleanOptionalAction, default=False, help="即使已有 instructions_json 也重跑")
    p_llm.set_defaults(func=cmd_llm_effects)

    p_serve = sub.add_parser("serve", help="啟動本地瀏覽介面（HTTP）")
    p_serve.add_argument("--db", default="ptcg_tw.sqlite", help="SQLite 檔案路徑")
    p_serve.add_argument("--host", default="127.0.0.1", help="監聽位址（預設 127.0.0.1）")
    p_serve.add_argument("--port", default=8000, type=int, help="監聽埠號（預設 8000）")
    p_serve.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
