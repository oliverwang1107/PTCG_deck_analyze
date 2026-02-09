from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .db import Skill
from .effects import normalize_text


BASE_URL = "https://asia.pokemon-card.com"
LIST_PATH = "/tw/card-search/list/"
DETAIL_PATH_PREFIX = "/tw/card-search/detail/"

DEFAULT_HEADERS = {
    "User-Agent": "ptcg-tw-localdb/0.1 (+https://example.invalid)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.3",
}

DEFAULT_TIMEOUT_S = 30
DEFAULT_RETRIES = 3
_RETRY_STATUS = {429, 500, 502, 503, 504}

_DETAIL_ID_RE = re.compile(r"/tw/card-search/detail/(\d+)/")


class RateLimiter:
    def __init__(self, min_interval_s: float) -> None:
        self._min_interval_s = max(0.0, float(min_interval_s))
        self._lock = threading.Lock()
        self._next_ok_at = 0.0

    def wait(self) -> None:
        if self._min_interval_s <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next_ok_at:
                time.sleep(self._next_ok_at - now)
            self._next_ok_at = max(self._next_ok_at, now) + self._min_interval_s


@dataclass(frozen=True)
class SearchParams:
    keyword: str = ""
    card_type: str = "all"  # all|1(pokemon)|2(trainers)|3(energy)
    regulation: str = "all"  # 1|2|3|all


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def _request_with_retry(
    session: requests.Session,
    limiter: RateLimiter,
    method: str,
    url: str,
    *,
    retries: int = DEFAULT_RETRIES,
    backoff_s: float = 1.0,
    **kwargs: Any,
) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(max(1, int(retries))):
        limiter.wait()
        try:
            resp = session.request(method, url, timeout=DEFAULT_TIMEOUT_S, **kwargs)
            if resp.status_code in _RETRY_STATUS:
                if attempt >= retries - 1:
                    resp.raise_for_status()
                time.sleep(backoff_s * (2**attempt))
                continue
            resp.raise_for_status()
            return resp
        except (requests.RequestException, OSError) as e:
            last_exc = e
            if attempt >= retries - 1:
                raise
            time.sleep(backoff_s * (2**attempt))
            continue
    if last_exc:
        raise last_exc
    raise RuntimeError("request failed without exception")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _energy_code_from_img_src(src: str | None) -> str | None:
    if not src:
        return None
    try:
        stem = Path(urlparse(src).path).stem
    except Exception:
        return None
    return stem or None


def _safe_text(el: Any) -> str | None:
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    return text or None


def _safe_text_lines(el: Any) -> str | None:
    if el is None:
        return None
    text = el.get_text("\n", strip=True)
    return text or None


def extract_card_ids_from_list_html(html: str) -> list[int]:
    ids = _DETAIL_ID_RE.findall(html)
    # Preserve order but de-duplicate
    unique: dict[str, None] = {}
    for cid in ids:
        unique[cid] = None
    return [int(cid) for cid in unique.keys()]


def extract_total_pages_from_list_html(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("p.resultTotalPages")
    if node:
        digits = re.findall(r"\d+", node.get_text(" ", strip=True))
        if digits:
            return int(digits[-1])

    # Fallback: look at pagination URLs
    max_page = 0
    for a in soup.select("nav.pagination a[href]"):
        href = a.get("href") or ""
        m = re.search(r"[?&]pageNo=(\d+)", href)
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page or None


def start_search(
    session: requests.Session,
    limiter: RateLimiter,
    params: SearchParams,
) -> tuple[str, int | None]:
    """
    POST 一次到 list/ 以建立搜尋條件（伺服器會用 cookie 保留條件），並回傳 page 1 HTML 與 total_pages。
    """
    resp = _request_with_retry(
        session,
        limiter,
        "POST",
        urljoin(BASE_URL, LIST_PATH),
        data={"keyword": params.keyword, "cardType": params.card_type, "regulation": params.regulation},
    )
    html = resp.text
    return html, extract_total_pages_from_list_html(html)


def fetch_list_page(
    session: requests.Session,
    limiter: RateLimiter,
    page_no: int,
) -> str:
    resp = _request_with_retry(
        session,
        limiter,
        "GET",
        urljoin(BASE_URL, LIST_PATH),
        params={"pageNo": str(page_no)},
    )
    return resp.text


def fetch_detail_html(
    session: requests.Session,
    limiter: RateLimiter,
    card_id: int,
) -> str | None:
    url = urljoin(BASE_URL, f"{DETAIL_PATH_PREFIX}{card_id}/")
    resp = _request_with_retry(session, limiter, "GET", url, allow_redirects=True)
    final_url = str(resp.url)
    # 不存在時常會被導回 list/
    if final_url.rstrip("/").endswith(LIST_PATH.rstrip("/")):
        return None
    return resp.text


def parse_card_detail_html(card_id: int, html: str) -> tuple[dict[str, Any], list[Skill]]:
    soup = BeautifulSoup(html, "html.parser")

    source_url = urljoin(BASE_URL, f"{DETAIL_PATH_PREFIX}{card_id}/")

    h1 = soup.select_one("h1.pageHeader.cardDetail")
    evolve_marker = _safe_text(h1.select_one("span.evolveMarker")) if h1 else None
    name_parts: list[str] = []
    if h1:
        for s in h1.stripped_strings:
            name_parts.append(str(s))
    if evolve_marker and name_parts and name_parts[0] == evolve_marker:
        name_parts = name_parts[1:]
    name = "".join(name_parts).strip()

    image_url = soup.select_one("section.imageColumn img")
    image_url = image_url.get("src") if image_url else None

    main_info = soup.select_one("p.mainInfomation")
    hp: int | None = None
    element_code: str | None = None
    element: str | None = None
    if main_info:
        hp_node = main_info.select_one("span.number")
        if hp_node:
            hp_text = hp_node.get_text(strip=True)
            if hp_text.isdigit():
                hp = int(hp_text)
        element_node = main_info.select_one("span.type")
        element = element_node.get_text(strip=True) if element_node else None
        element_img = main_info.select_one("img")
        element_code = _energy_code_from_img_src(element_img.get("src") if element_img else None)

    # Skills / effects
    skills: list[Skill] = []
    skill_index = 0
    for block in soup.select("div.skillInformation"):
        kind = _safe_text(block.select_one("h3.commonHeader"))
        for skill in block.select("div.skill"):
            name_txt = _safe_text(skill.select_one("span.skillName"))
            damage_txt = _safe_text(skill.select_one("span.skillDamage"))
            effect_txt = _safe_text_lines(skill.select_one("p.skillEffect"))
            effect_norm = normalize_text(effect_txt)
            cost_codes: list[str] = []
            for img in skill.select("span.skillCost img"):
                code = _energy_code_from_img_src(img.get("src"))
                if code:
                    cost_codes.append(code)
            skills.append(
                Skill(
                    idx=skill_index,
                    kind=kind,
                    name=name_txt,
                    cost=cost_codes,
                    damage=damage_txt,
                    effect=effect_txt,
                    effect_text_norm=effect_norm,
                )
            )
            skill_index += 1

    # Weakness / resistance / retreat (Pokemon only)
    weakness_code = weakness_value = None
    resistance_code = resistance_value = None
    retreat_cost: int | None = None
    sub = soup.select_one("div.subInformation")
    if sub:
        weak_td = sub.select_one("td.weakpoint")
        if weak_td:
            img = weak_td.select_one("img")
            weakness_code = _energy_code_from_img_src(img.get("src") if img else None)
            txt = weak_td.get_text(" ", strip=True)
            txt = re.sub(r"\s+", " ", txt).strip()
            if weakness_code:
                txt = txt.replace(weakness_code, "").strip()
            weakness_value = txt or None

        resist_td = sub.select_one("td.resist")
        if resist_td:
            img = resist_td.select_one("img")
            resistance_code = _energy_code_from_img_src(img.get("src") if img else None)
            txt = resist_td.get_text(" ", strip=True)
            txt = re.sub(r"\s+", " ", txt).strip()
            if resistance_code:
                txt = txt.replace(resistance_code, "").strip()
            resistance_value = txt or None

        escape_td = sub.select_one("td.escape")
        if escape_td:
            retreat_cost = len(escape_td.select("img"))

    # Expansion / regulation mark
    expansion_symbol_url = None
    regulation_mark = None
    collector_number = None
    expansion = soup.select_one("section.expansionColumn")
    if expansion:
        sym = expansion.select_one("span.expansionSymbol img")
        expansion_symbol_url = sym.get("src") if sym else None
        alpha = expansion.select_one("span.alpha")
        regulation_mark = alpha.get_text(" ", strip=True) if alpha else None
        cno = expansion.select_one("span.collectorNumber")
        collector_number = cno.get_text(" ", strip=True) if cno else None

    # Expansion link / code
    expansion_code = None
    expansion_name = None
    exp_link = soup.select_one("section.expansionLinkColumn a[href]")
    if exp_link:
        expansion_name = exp_link.get_text(" ", strip=True) or None
        href = exp_link.get("href") or ""
        qs = parse_qs(urlparse(href).query)
        codes = qs.get("expansionCodes")
        if codes:
            expansion_code = codes[0]

    # Illustrator
    illustrator = None
    ill = soup.select_one("div.illustrator a")
    if ill:
        illustrator = ill.get_text(" ", strip=True) or None

    # Pokemon extra info (No., height, weight, description)
    pokedex_no: int | None = None
    height_m: float | None = None
    weight_kg: float | None = None
    description: str | None = None

    extra = soup.select_one("div.extraInformation")
    if extra:
        h3 = extra.select_one("h3")
        if h3:
            m = re.search(r"No\.(\d+)", h3.get_text(" ", strip=True))
            if m:
                pokedex_no = int(m.group(1))
        size = extra.select_one("p.size")
        if size:
            values = [v.get_text(" ", strip=True) for v in size.select("span.value")]
            if len(values) >= 1:
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", values[0])
                if m:
                    height_m = float(m.group(1))
            if len(values) >= 2:
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", values[1])
                if m:
                    weight_kg = float(m.group(1))
        description = _safe_text_lines(extra.select_one("p.discription"))

    # card_type heuristic
    card_type = None
    if main_info:
        card_type = "pokemon"
    else:
        headers = [
            (h.get_text(" ", strip=True) or "")
            for h in soup.select("div.skillInformation h3.commonHeader")
        ]
        header_text = " ".join(headers)
        if any(k in header_text for k in ["能量"]):
            card_type = "energy"
        elif any(k in header_text for k in ["訓練家", "物品", "支援者", "場地", "寶可夢道具"]):
            card_type = "trainer"
        else:
            card_type = "unknown"

    card: dict[str, Any] = {
        "card_id": card_id,
        "name": name,
        "evolve_marker": evolve_marker,
        "card_type": card_type,
        "hp": hp,
        "element_code": element_code,
        "element": element,
        "regulation_mark": regulation_mark,
        "collector_number": collector_number,
        "expansion_code": expansion_code,
        "expansion_name": expansion_name,
        "expansion_symbol_url": expansion_symbol_url,
        "illustrator": illustrator,
        "image_url": image_url,
        "weakness_code": weakness_code,
        "weakness_value": weakness_value,
        "resistance_code": resistance_code,
        "resistance_value": resistance_value,
        "retreat_cost": retreat_cost,
        "pokedex_no": pokedex_no,
        "height_m": height_m,
        "weight_kg": weight_kg,
        "description": description,
        "source_url": source_url,
        "fetched_at": _utc_now_iso(),
        "skills": [
            {
                "idx": s.idx,
                "kind": s.kind,
                "name": s.name,
                "cost": s.cost,
                "damage": s.damage,
                "effect": s.effect,
            }
            for s in skills
        ],
    }
    return card, skills
