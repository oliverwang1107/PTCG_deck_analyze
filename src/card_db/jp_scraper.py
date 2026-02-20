"""Scraper for Japanese official PTCG site (www.pokemon-card.com)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .db import Skill
from .scraper import RateLimiter, _request_with_retry, DEFAULT_HEADERS

JP_BASE_URL = "https://www.pokemon-card.com"
JP_DETAIL_PATH = "/card-search/details.php/card/{card_id}/regu/ALL"

# Map CSS class suffixes to energy codes (matching TW scraper conventions)
_ICON_TO_CODE: dict[str, str] = {
    "grass": "grass",
    "fire": "fire",
    "water": "water",
    "electric": "lightning",
    "psychic": "psychic",
    "fighting": "fighting",
    "dark": "dark",
    "steel": "steel",
    "fairy": "fairy",
    "dragon": "dragon",
    "none": "colorless",
}

_ICON_CLASS_RE = re.compile(r"icon-(\w+)")


def _energy_code_from_icon_class(el: Any) -> str | None:
    """Extract energy code from a <span class="icon-dark icon"> element."""
    if el is None:
        return None
    classes = el.get("class", [])
    for cls in classes:
        m = _ICON_CLASS_RE.match(cls)
        if m:
            key = m.group(1)
            return _ICON_TO_CODE.get(key, key)
    return None


def _safe_text(el: Any) -> str | None:
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    return text or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_jp_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "ptcg-jp-localdb/0.1 (+https://example.invalid)",
        "Accept-Language": "ja,en;q=0.3",
    })
    return s


def fetch_jp_detail_html(
    session: requests.Session,
    limiter: RateLimiter,
    card_id: int,
) -> str | None:
    """Fetch a single JP card detail page. Returns HTML or None if not found."""
    url = JP_BASE_URL + JP_DETAIL_PATH.format(card_id=card_id)
    resp = _request_with_retry(session, limiter, "GET", url, allow_redirects=True)
    # Check if redirected away from detail page
    final_url = str(resp.url)
    if "details.php" not in final_url and "detail" not in final_url:
        return None
    return resp.text


def parse_jp_card_detail_html(card_id: int, html: str) -> tuple[dict[str, Any], list[Skill]]:
    """Parse a JP card detail page and return (card_dict, skills_list).

    The output schema matches the TW scraper so the same DB can store both.
    """
    soup = BeautifulSoup(html, "html.parser")
    source_url = JP_BASE_URL + JP_DETAIL_PATH.format(card_id=card_id)

    # --- Card name ---
    h1 = soup.select_one("h1.Heading1")
    name = h1.get_text(strip=True) if h1 else ""

    # --- Image URL ---
    img_el = soup.select_one("img.fit")
    image_url = None
    if img_el:
        src = img_el.get("src", "")
        image_url = urljoin(JP_BASE_URL, src) if src else None

    # --- Expansion code & collector number ---
    expansion_code = None
    collector_number = None
    subtext = soup.select_one("div.subtext")
    if subtext:
        # Expansion code from regulation logo image like SV2a.gif
        reg_img = subtext.select_one("img.img-regulation")
        if reg_img:
            alt = reg_img.get("alt", "")
            if alt:
                expansion_code = alt.strip()

        # Collector number from text like "110 / 165"
        text = subtext.get_text(" ", strip=True)
        # Remove expansion code text if present
        if expansion_code:
            text = text.replace(expansion_code, "").strip()
        m = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if m:
            collector_number = f"{m.group(1)}/{m.group(2)}"

    # --- Expansion name ---
    expansion_name = None
    sub_section = soup.select_one("section.SubSection")
    if sub_section:
        exp_link = sub_section.select_one("a.Link")
        if exp_link:
            expansion_name = exp_link.get_text(strip=True) or None

    # --- HP, type, evolve marker ---
    hp: int | None = None
    element_code: str | None = None
    element: str | None = None
    evolve_marker: str | None = None

    top_info = soup.select_one("div.TopInfo")
    if top_info:
        hp_el = top_info.select_one("span.hp-num")
        if hp_el:
            hp_text = hp_el.get_text(strip=True)
            if hp_text.isdigit():
                hp = int(hp_text)

        type_el = top_info.select_one("span.type")
        if type_el:
            evolve_marker = type_el.get_text(strip=True) or None

        # Element from icon class
        icon_el = top_info.select_one("span.hp-type + span[class*='icon-']")
        if icon_el is None:
            icon_el = top_info.select_one("span[class*='icon-']")
        element_code = _energy_code_from_icon_class(icon_el)
        if element_code:
            element = element_code  # JP uses element code as name

    # --- Skills ---
    skills: list[Skill] = []
    skill_index = 0

    # In JP pages, skills are flat <h2> + <h4> pairs inside RightBox-inner
    right_box = soup.select_one("div.RightBox-inner")
    if right_box:
        current_kind: str | None = None
        # Iterate through h2 and h4 elements
        for el in right_box.find_all(["h2", "h4", "p"]):
            if el.name == "h2":
                current_kind = el.get_text(strip=True) or None
                continue

            if el.name == "h4":
                # Parse skill name, cost icons, and damage
                cost_codes: list[str] = []
                for icon_span in el.find_all("span", class_=_ICON_CLASS_RE):
                    code = _energy_code_from_icon_class(icon_span)
                    if code:
                        cost_codes.append(code)

                # Damage from <span class="f_right">
                damage_el = el.select_one("span.f_right")
                damage = damage_el.get_text(strip=True) if damage_el else None

                # Skill name: text content minus icons and damage
                name_txt = ""
                for child in el.children:
                    if hasattr(child, "get") and (
                        "icon" in " ".join(child.get("class", []))
                        or "f_right" in " ".join(child.get("class", []))
                    ):
                        continue
                    text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                    name_txt += text
                name_txt = name_txt.strip()

                # The next <p> sibling is the effect text
                effect_el = el.find_next_sibling("p")
                effect = effect_el.get_text("\n", strip=True) if effect_el else None

                skills.append(Skill(
                    idx=skill_index,
                    kind=current_kind,
                    name=name_txt or None,
                    cost=cost_codes,
                    damage=damage,
                    effect=effect,
                    effect_text_norm=None,
                ))
                skill_index += 1

    # --- Weakness / Resistance / Retreat ---
    weakness_code = weakness_value = None
    resistance_code = resistance_value = None
    retreat_cost: int | None = None

    info_table = right_box.select_one("table") if right_box else None
    if info_table:
        rows = info_table.select("tr")
        if len(rows) >= 2:
            tds = rows[1].select("td")
            # Weakness
            if len(tds) >= 1:
                w_td = tds[0]
                w_icon = w_td.select_one("span[class*='icon-']")
                weakness_code = _energy_code_from_icon_class(w_icon)
                w_text = w_td.get_text(strip=True)
                if weakness_code:
                    weakness_value = w_text.replace("--", "").strip() or None
                elif w_text != "--":
                    weakness_value = w_text or None

            # Resistance
            if len(tds) >= 2:
                r_td = tds[1]
                r_icon = r_td.select_one("span[class*='icon-']")
                resistance_code = _energy_code_from_icon_class(r_icon)
                r_text = r_td.get_text(strip=True)
                if resistance_code:
                    resistance_value = r_text.replace("--", "").strip() or None
                elif r_text != "--":
                    resistance_value = r_text or None

            # Retreat
            if len(tds) >= 3:
                e_td = tds[2]
                retreat_cost = len(e_td.select("span[class*='icon-']"))

    # --- Pokedex info ---
    pokedex_no: int | None = None
    height_m: float | None = None
    weight_kg: float | None = None
    description: str | None = None

    card_div = soup.select_one("div.card")
    if card_div:
        h4 = card_div.select_one("h4")
        if h4:
            m = re.search(r"No\.(\d+)", h4.get_text(strip=True))
            if m:
                pokedex_no = int(m.group(1))
        ps = card_div.select("p")
        for p in ps:
            text = p.get_text(strip=True)
            hm = re.search(r"高さ[：:]?\s*([0-9.]+)\s*m", text)
            if hm:
                height_m = float(hm.group(1))
            wm = re.search(r"重さ[：:]?\s*([0-9.]+)\s*kg", text)
            if wm:
                weight_kg = float(wm.group(1))
        # Last <p> in card div that has substantial text is usually the description
        if len(ps) >= 2:
            desc_text = ps[-1].get_text(strip=True)
            if desc_text and "高さ" not in desc_text and "重さ" not in desc_text:
                description = desc_text

    # --- Card type heuristic ---
    card_type = None
    if top_info and hp is not None:
        card_type = "pokemon"
    else:
        # Check skill kinds for trainer/energy
        kind_texts = [s.kind or "" for s in skills]
        all_kinds = " ".join(kind_texts)
        if "エネルギー" in all_kinds:
            card_type = "energy"
        elif any(k in all_kinds for k in ["トレーナーズ", "グッズ", "サポート", "スタジアム", "ポケモンのどうぐ"]):
            card_type = "trainer"
        else:
            card_type = "unknown"

    # --- Illustrator ---
    illustrator = None
    author_div = soup.select_one("div.author")
    if author_div:
        a = author_div.select_one("a")
        illustrator = a.get_text(strip=True) if a else None

    # --- Regulation mark ---
    # JP pages don't display regulation letter explicitly, but expansion_code
    # like SV2a implies the regulation era. We leave it None for now.
    regulation_mark = None

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
        "expansion_symbol_url": None,
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
