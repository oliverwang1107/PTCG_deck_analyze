from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse


ENERGY_ICON_BASE = "https://asia.pokemon-card.com/various_images/energy/"


def _icon(code: str, *, size: int = 18) -> str:
    src = f"{ENERGY_ICON_BASE}{escape(code)}.png"
    return f'<img alt="{escape(code)}" src="{src}" width="{size}" height="{size}" loading="lazy">'


def _css() -> str:
    return """
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Noto Sans, Arial, sans-serif; margin: 0; }
    a { color: inherit; }
    header { padding: 16px 20px; border-bottom: 1px solid rgba(127,127,127,.3); position: sticky; top: 0; background: rgba(255,255,255,.9); backdrop-filter: blur(8px); }
    main { padding: 18px 20px 40px; max-width: 1100px; margin: 0 auto; }
    .row { display: grid; grid-template-columns: 340px 1fr; gap: 22px; align-items: start; }
    .cardimg { width: 100%; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,.18); background: rgba(127,127,127,.1); }
    .title { font-size: 26px; font-weight: 800; margin: 0 0 12px; letter-spacing: .2px; }
    .pill { display: inline-block; padding: 2px 10px; border-radius: 999px; border: 1px solid rgba(127,127,127,.35); font-size: 12px; margin-right: 8px; opacity: .85; }
    .kv { display: grid; grid-template-columns: 130px 1fr; gap: 8px 12px; margin: 12px 0 0; }
    .k { opacity: .75; }
    .skills { margin-top: 14px; display: grid; gap: 12px; }
    .skill { border: 1px solid rgba(127,127,127,.28); border-radius: 12px; padding: 12px 14px; }
    .skillhead { display: flex; gap: 10px; flex-wrap: wrap; align-items: baseline; }
    .skillname { font-weight: 800; }
    .cost { display: inline-flex; gap: 4px; align-items: center; opacity: .9; }
    .dmg { margin-left: auto; font-weight: 900; }
    .effect { margin: 8px 0 0; white-space: pre-line; opacity: .92; }
    .search { display: flex; gap: 10px; align-items: center; }
    input[type=text] { width: min(520px, 70vw); padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(127,127,127,.35); background: rgba(127,127,127,.08); }
    button { padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(127,127,127,.35); background: rgba(127,127,127,.12); cursor: pointer; }
    .grid { margin-top: 14px; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 14px; }
    .item { border: 1px solid rgba(127,127,127,.28); border-radius: 14px; padding: 10px; text-decoration: none; }
    .thumb { width: 100%; aspect-ratio: 63/88; object-fit: contain; background: rgba(127,127,127,.08); border-radius: 10px; }
    .meta { margin-top: 8px; display: grid; gap: 4px; }
    .small { font-size: 12px; opacity: .78; }
    .filters { display: grid; grid-template-columns: 1fr 160px 160px 160px; gap: 10px; align-items: center; flex-wrap: wrap; }
    select { padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(127,127,127,.35); background: rgba(127,127,127,.08); }
    .pager { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; gap: 10px; }
    .pager a { text-decoration: none; border: 1px solid rgba(127,127,127,.28); padding: 8px 12px; border-radius: 10px; }
    .pager .disabled { opacity: .4; pointer-events: none; }
    .topline { display:flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
    .muted { opacity: .75; }
    details { border: 1px solid rgba(127,127,127,.28); border-radius: 12px; padding: 10px 12px; margin-top: 14px; }
    summary { cursor: pointer; font-weight: 800; }
    pre { overflow: auto; padding: 10px; border-radius: 10px; background: rgba(127,127,127,.08); }
    .navrow { display:flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin: 10px 0 0; }
    .navrow a { text-decoration:none; border: 1px solid rgba(127,127,127,.28); padding: 8px 12px; border-radius: 10px; }
    .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.65); display: none; align-items: center; justify-content: center; padding: 18px; z-index: 50; }
    .overlay img { max-width: min(800px, 95vw); max-height: 92vh; border-radius: 12px; background: rgba(255,255,255,.05); }
    @media (prefers-color-scheme: dark) {
      header { background: rgba(24,24,24,.75); }
    }
    @media (max-width: 860px) {
      .row { grid-template-columns: 1fr; }
      .filters { grid-template-columns: 1fr 1fr; }
    }
    """


def _js() -> str:
    return """
    (() => {
      const overlay = document.getElementById('overlay');
      const overlayImg = document.getElementById('overlayImg');
      const cardImg = document.getElementById('cardImg');
      if (overlay && overlayImg && cardImg) {
        cardImg.addEventListener('click', () => {
          overlayImg.src = cardImg.src;
          overlay.style.display = 'flex';
        });
        overlay.addEventListener('click', () => {
          overlay.style.display = 'none';
          overlayImg.src = '';
        });
        document.addEventListener('keydown', (e) => {
          if (e.key === 'Escape') {
            overlay.style.display = 'none';
            overlayImg.src = '';
          }
        });
      }
    })();
    """


def _html_page(*, title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{_css()}</style>
</head>
<body>
  <header>
    <div class="search">
      <a href="/" style="text-decoration:none;font-weight:900;">PTCG 繁中卡牌資料庫</a>
      <span style="opacity:.7;">(local)</span>
    </div>
  </header>
  <main>{body}</main>
  <script>{_js()}</script>
</body>
</html>"""


@dataclass
class ServerConfig:
    db_path: Path


class Handler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer  # type: ignore[assignment]

    def _send(self, code: int, content: str, *, content_type: str = "text/html; charset=utf-8") -> None:
        data = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _conn(self) -> sqlite3.Connection:
        cfg: ServerConfig = self.server.cfg  # type: ignore[attr-defined]
        conn = sqlite3.connect(str(cfg.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        try:
            if path == "/":
                self._handle_index(qs)
                return
            if path.startswith("/card/"):
                card_id_str = path.split("/", 2)[2]
                self._handle_card(card_id_str, qs)
                return
            if path == "/api/cards":
                self._handle_api_cards(qs)
                return
            if path.startswith("/api/card/"):
                card_id_str = path.split("/", 3)[3] if path.count("/") >= 3 else ""
                self._handle_api_card(card_id_str)
                return
        except Exception as e:  # noqa: BLE001
            self._send(500, _html_page(title="Error", body=f"<pre>{escape(str(e))}</pre>"))
            return

        self._send(404, _html_page(title="Not Found", body="<p>404</p>"))

    def _get_int(self, qs: dict[str, list[str]], key: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
        raw = (qs.get(key) or [str(default)])[0]
        try:
            v = int(raw)
        except Exception:
            v = default
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        return v

    def _qs_str(self, qs: dict[str, list[str]], key: str, default: str = "") -> str:
        return (qs.get(key) or [default])[0].strip()

    def _make_query(self, **kwargs: Any) -> str:
        flat: dict[str, str] = {}
        for k, v in kwargs.items():
            if v is None:
                continue
            s = str(v).strip()
            if s == "":
                continue
            flat[k] = s
        return urlencode(flat)

    def _handle_index(self, qs: dict[str, list[str]]) -> None:
        q = self._qs_str(qs, "q", "")
        card_type = self._qs_str(qs, "type", "")
        mark = self._qs_str(qs, "mark", "")
        expansion = self._qs_str(qs, "exp", "")
        sort = self._qs_str(qs, "sort", "new")
        page = self._get_int(qs, "page", 1, lo=1)
        page_size = self._get_int(qs, "size", 60, lo=12, hi=120)
        offset = (page - 1) * page_size

        where: list[str] = []
        params: list[Any] = []
        if q:
            where.append("name LIKE ?")
            params.append(f"%{q}%")
        if card_type:
            where.append("card_type = ?")
            params.append(card_type)
        if mark:
            where.append("regulation_mark = ?")
            params.append(mark)
        if expansion:
            where.append("expansion_code = ?")
            params.append(expansion)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        order_sql = "ORDER BY card_id DESC" if sort == "new" else "ORDER BY card_id ASC"

        with self._conn() as conn:
            total = conn.execute(f"SELECT COUNT(1) AS c FROM cards {where_sql};", params).fetchone()["c"]
            rows = conn.execute(
                f"""
                SELECT card_id, name, image_url, expansion_code, collector_number, card_type, regulation_mark
                FROM cards
                {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?;
                """,
                [*params, page_size, offset],
            ).fetchall()

            # For filter dropdowns (stable, cached by DB content)
            marks = [
                r["regulation_mark"]
                for r in conn.execute(
                    "SELECT DISTINCT regulation_mark FROM cards WHERE regulation_mark IS NOT NULL ORDER BY regulation_mark ASC;"
                ).fetchall()
                if r["regulation_mark"]
            ]
            exps = [
                r["expansion_code"]
                for r in conn.execute(
                    "SELECT DISTINCT expansion_code FROM cards WHERE expansion_code IS NOT NULL ORDER BY expansion_code ASC;"
                ).fetchall()
                if r["expansion_code"]
            ]

        items = []
        for r in rows:
            cid = int(r["card_id"])
            name = r["name"] or ""
            img = r["image_url"] or ""
            exp = r["expansion_code"] or ""
            cno = r["collector_number"] or ""
            ctype = r["card_type"] or ""
            rmark = r["regulation_mark"] or ""
            link_qs = self._make_query(q=q, type=card_type, mark=mark, exp=expansion, sort=sort, page=page, size=page_size)
            items.append(
                f"""
                <a class="item" href="/card/{cid}?{link_qs}">
                  <img class="thumb" src="{escape(img)}" alt="{escape(name)}" loading="lazy">
                  <div class="meta">
                    <div style="font-weight:800;line-height:1.2;">{escape(name)}</div>
                    <div class="small">{escape(exp)} {escape(cno)}</div>
                    <div class="small">{escape(ctype)} {escape(rmark)}</div>
                  </div>
                </a>
                """
            )

        results_html = "".join(items) if items else '<p style="opacity:.7;">沒有結果</p>'
        total_pages = max(1, (int(total) + page_size - 1) // page_size)
        page = min(page, total_pages)
        prev_qs = self._make_query(q=q, type=card_type, mark=mark, exp=expansion, sort=sort, page=page - 1, size=page_size) if page > 1 else ""
        next_qs = self._make_query(q=q, type=card_type, mark=mark, exp=expansion, sort=sort, page=page + 1, size=page_size) if page < total_pages else ""

        def _opt(value: str, label: str, current: str) -> str:
            sel = " selected" if value == current else ""
            return f'<option value="{escape(value)}"{sel}>{escape(label)}</option>'

        mark_opts = [_opt("", "全部卡標", mark)] + [_opt(m, m, mark) for m in marks]
        exp_opts = [_opt("", "全部系列", expansion)] + [_opt(e, e, expansion) for e in exps]
        type_opts = [
            _opt("", "全部類型", card_type),
            _opt("pokemon", "寶可夢", card_type),
            _opt("trainer", "訓練家", card_type),
            _opt("energy", "能量", card_type),
            _opt("unknown", "未知", card_type),
        ]
        sort_opts = [_opt("new", "最新優先", sort), _opt("old", "最舊優先", sort)]
        size_opts = [
            _opt("24", "24/頁", str(page_size)),
            _opt("60", "60/頁", str(page_size)),
            _opt("120", "120/頁", str(page_size)),
        ]

        body = f"""
        <div class="topline">
          <form method="GET" action="/" style="flex: 1;">
            <div class="filters">
              <input type="text" name="q" value="{escape(q)}" placeholder="輸入卡名關鍵字（例：皮卡丘 / 阿響）">
              <select name="type">{''.join(type_opts)}</select>
              <select name="mark">{''.join(mark_opts)}</select>
              <select name="exp">{''.join(exp_opts)}</select>
              <select name="sort">{''.join(sort_opts)}</select>
              <select name="size">{''.join(size_opts)}</select>
              <input type="hidden" name="page" value="1">
              <button type="submit">搜尋/套用</button>
            </div>
          </form>
          <div class="muted">共 {int(total)} 張</div>
        </div>

        <div class="grid">{results_html}</div>
        <div class="pager">
          <a class="{ 'disabled' if page <= 1 else '' }" href="/?{prev_qs}">← 上一頁</a>
          <div class="muted">第 {page} / {total_pages} 頁</div>
          <a class="{ 'disabled' if page >= total_pages else '' }" href="/?{next_qs}">下一頁 →</a>
        </div>
        """
        self._send(200, _html_page(title="PTCG Cards", body=body))

    def _handle_card(self, card_id_str: str, qs: dict[str, list[str]]) -> None:
        if not card_id_str.isdigit():
            self._send(400, _html_page(title="Bad Request", body="<p>bad card id</p>"))
            return
        card_id = int(card_id_str)

        # Preserve "back" context
        back_q = self._qs_str(qs, "q", "")
        back_type = self._qs_str(qs, "type", "")
        back_mark = self._qs_str(qs, "mark", "")
        back_exp = self._qs_str(qs, "exp", "")
        back_sort = self._qs_str(qs, "sort", "new")
        back_page = self._get_int(qs, "page", 1, lo=1)
        back_size = self._get_int(qs, "size", 60, lo=12, hi=120)
        back_href = "/?" + self._make_query(q=back_q, type=back_type, mark=back_mark, exp=back_exp, sort=back_sort, page=back_page, size=back_size)

        with self._conn() as conn:
            card = conn.execute("SELECT * FROM cards WHERE card_id = ?;", (card_id,)).fetchone()
            if card is None:
                self._send(404, _html_page(title="Not Found", body="<p>card not found</p>"))
                return
            skills = conn.execute(
                """
                SELECT idx, kind, name, cost_json, damage, effect
                FROM skills
                WHERE card_id = ?
                ORDER BY idx ASC;
                """,
                (card_id,),
            ).fetchall()

            # Stable navigation: next/prev within current filter context if any; otherwise by card_id.
            where: list[str] = []
            params: list[Any] = []
            if back_q:
                where.append("name LIKE ?")
                params.append(f"%{back_q}%")
            if back_type:
                where.append("card_type = ?")
                params.append(back_type)
            if back_mark:
                where.append("regulation_mark = ?")
                params.append(back_mark)
            if back_exp:
                where.append("expansion_code = ?")
                params.append(back_exp)
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            order_sql = "ORDER BY card_id DESC" if back_sort == "new" else "ORDER BY card_id ASC"
            ids = [
                int(r["card_id"])
                for r in conn.execute(
                    f"SELECT card_id FROM cards {where_sql} {order_sql};",
                    params,
                ).fetchall()
            ]
            prev_id = next_id = None
            if ids:
                try:
                    idx = ids.index(card_id)
                except ValueError:
                    idx = -1
                if idx >= 0:
                    if idx > 0:
                        prev_id = ids[idx - 1]
                    if idx < len(ids) - 1:
                        next_id = ids[idx + 1]

        name = card["name"] or ""
        img = card["image_url"] or ""

        pills = []
        if card["evolve_marker"]:
            pills.append(f'<span class="pill">{escape(card["evolve_marker"])}</span>')
        if card["card_type"]:
            pills.append(f'<span class="pill">{escape(card["card_type"])}</span>')
        if card["hp"] is not None:
            pills.append(f'<span class="pill">HP {int(card["hp"])}</span>')
        if card["element_code"]:
            pills.append(f'<span class="pill">{_icon(card["element_code"], size=16)} {escape(card["element"] or card["element_code"] or "")}</span>')

        kv_rows = []
        for k, v in [
            ("規則標記", card["regulation_mark"]),
            ("系列", f"{card['expansion_code'] or ''} {card['expansion_name'] or ''}".strip() or None),
            ("卡號", card["collector_number"]),
            ("插畫家", card["illustrator"]),
            ("弱點", None if card["weakness_value"] in (None, "--") else f"{_icon(card['weakness_code'], size=16) if card['weakness_code'] else ''} {escape(card['weakness_value'])}"),
            ("抵抗力", None if card["resistance_value"] in (None, "--") else f"{_icon(card['resistance_code'], size=16) if card['resistance_code'] else ''} {escape(card['resistance_value'])}"),
            (
                "撤退",
                None
                if card["retreat_cost"] is None
                else (
                    "0"
                    if int(card["retreat_cost"]) == 0
                    else f"{''.join(_icon('Colorless', size=16) for _ in range(int(card['retreat_cost'])))}"
                ),
            ),
            ("No.", None if card["pokedex_no"] is None else f"No.{int(card['pokedex_no'])}"),
            ("身高", None if card["height_m"] is None else f"{card['height_m']} m"),
            ("體重", None if card["weight_kg"] is None else f"{card['weight_kg']} kg"),
        ]:
            if v:
                kv_rows.append(f'<div class="k">{escape(k)}</div><div class="v">{v}</div>')

        skill_html = []
        for s in skills:
            kind = s["kind"] or ""
            sname = s["name"] or ""
            dmg = s["damage"] or ""
            effect = s["effect"] or ""
            try:
                cost = json.loads(s["cost_json"] or "[]")
            except Exception:
                cost = []
            cost_icons = "".join(_icon(c, size=16) for c in cost) if isinstance(cost, list) else ""
            head_left = f'<span class="pill">{escape(kind)}</span>' if kind else ""
            skill_html.append(
                f"""
                <div class="skill">
                  <div class="skillhead">
                    {head_left}
                    <span class="skillname">{escape(sname) if sname else ""}</span>
                    <span class="cost">{cost_icons}</span>
                    <span class="dmg">{escape(dmg)}</span>
                  </div>
                  <div class="effect">{escape(effect)}</div>
                </div>
                """
            )

        desc = card["description"] or ""
        if desc:
            kv_rows.append(f'<div class="k">說明</div><div class="v" style="white-space:pre-line;">{escape(desc)}</div>')

        raw_json = ""
        try:
            raw = json.loads(card["raw_json"] or "{}")
            raw_json = json.dumps(raw, ensure_ascii=False, indent=2)
        except Exception:
            raw_json = str(card["raw_json"] or "")

        link_qs = self._make_query(q=back_q, type=back_type, mark=back_mark, exp=back_exp, sort=back_sort, page=back_page, size=back_size)
        prev_href = f"/card/{prev_id}?{link_qs}" if prev_id is not None else ""
        next_href = f"/card/{next_id}?{link_qs}" if next_id is not None else ""

        body = f"""
        <p><a href="{escape(back_href)}" style="opacity:.75;">← 回列表</a></p>
        <div class="navrow">
          <a class="{ 'disabled' if prev_id is None else '' }" href="{escape(prev_href)}">← 上一張</a>
          <div class="muted">card_id: {card_id}</div>
          <a class="{ 'disabled' if next_id is None else '' }" href="{escape(next_href)}">下一張 →</a>
        </div>
        <div class="row">
          <div>
            <img id="cardImg" class="cardimg" src="{escape(img)}" alt="{escape(name)}" loading="lazy" style="cursor: zoom-in;">
          </div>
          <div>
            <h1 class="title">{escape(name)}</h1>
            <div>{''.join(pills)}</div>
            <div class="kv">{''.join(kv_rows)}</div>
            <div class="skills">{''.join(skill_html)}</div>
            <details>
              <summary>Raw JSON（除錯/匯出用）</summary>
              <pre>{escape(raw_json)}</pre>
            </details>
          </div>
        </div>
        <div id="overlay" class="overlay"><img id="overlayImg" alt="zoom"></div>
        """
        self._send(200, _html_page(title=name, body=body))

    def _handle_api_cards(self, qs: dict[str, list[str]]) -> None:
        q = (qs.get("q") or [""])[0].strip()
        limit = int((qs.get("limit") or ["20"])[0])
        limit = max(1, min(200, limit))
        with self._conn() as conn:
            if q:
                rows = conn.execute(
                    """
                    SELECT card_id, name, image_url, expansion_code, collector_number, card_type
                    FROM cards
                    WHERE name LIKE ?
                    ORDER BY card_id DESC
                    LIMIT ?;
                    """,
                    (f"%{q}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT card_id, name, image_url, expansion_code, collector_number, card_type
                    FROM cards
                    ORDER BY card_id DESC
                    LIMIT ?;
                    """,
                    (limit,),
                ).fetchall()

        payload = [
            {
                "card_id": int(r["card_id"]),
                "name": r["name"],
                "image_url": r["image_url"],
                "expansion_code": r["expansion_code"],
                "collector_number": r["collector_number"],
                "card_type": r["card_type"],
            }
            for r in rows
        ]
        self._send(200, json.dumps(payload, ensure_ascii=False), content_type="application/json; charset=utf-8")

    def _handle_api_card(self, card_id_str: str) -> None:
        if not card_id_str.isdigit():
            self._send(400, json.dumps({"error": "bad card id"}), content_type="application/json; charset=utf-8")
            return
        card_id = int(card_id_str)
        with self._conn() as conn:
            card = conn.execute("SELECT * FROM cards WHERE card_id = ?;", (card_id,)).fetchone()
            if card is None:
                self._send(404, json.dumps({"error": "not found"}), content_type="application/json; charset=utf-8")
                return
            skills = conn.execute(
                """
                SELECT idx, kind, name, cost_json, damage, effect
                FROM skills
                WHERE card_id = ?
                ORDER BY idx ASC;
                """,
                (card_id,),
            ).fetchall()
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
        self._send(200, json.dumps(payload, ensure_ascii=False), content_type="application/json; charset=utf-8")


def serve(db_path: str | Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    cfg = ServerConfig(db_path=Path(db_path))
    httpd = ThreadingHTTPServer((host, int(port)), Handler)
    httpd.cfg = cfg  # type: ignore[attr-defined]
    print(f"Serving on http://{host}:{int(port)}/  (db={cfg.db_path})", flush=True)
    httpd.serve_forever()
