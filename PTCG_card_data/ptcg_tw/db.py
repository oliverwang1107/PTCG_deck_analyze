from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = str(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cards (
            card_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            evolve_marker TEXT,
            card_type TEXT,
            hp INTEGER,
            element_code TEXT,
            element TEXT,
            regulation_mark TEXT,
            collector_number TEXT,
            expansion_code TEXT,
            expansion_name TEXT,
            expansion_symbol_url TEXT,
            illustrator TEXT,
            image_url TEXT,
            weakness_code TEXT,
            weakness_value TEXT,
            resistance_code TEXT,
            resistance_value TEXT,
            retreat_cost INTEGER,
            pokedex_no INTEGER,
            height_m REAL,
            weight_kg REAL,
            description TEXT,
            source_url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
        CREATE INDEX IF NOT EXISTS idx_cards_expansion_code ON cards(expansion_code);
        CREATE INDEX IF NOT EXISTS idx_cards_collector_number ON cards(collector_number);

        CREATE TABLE IF NOT EXISTS skills (
            skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            idx INTEGER NOT NULL,
            kind TEXT,
            name TEXT,
            cost_json TEXT,
            damage TEXT,
            effect TEXT,
            effect_text_norm TEXT,
            instructions_json TEXT,
            FOREIGN KEY(card_id) REFERENCES cards(card_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_skills_card_id ON skills(card_id);
        """
    )

    # 兼容舊版：嘗試補充新欄位
    for alter in [
        "ALTER TABLE skills ADD COLUMN effect_text_norm TEXT;",
        "ALTER TABLE skills ADD COLUMN instructions_json TEXT;",
    ]:
        try:
            conn.execute(alter)
        except sqlite3.OperationalError:
            pass

    cur = conn.execute("SELECT value FROM meta WHERE key = 'schema_version';")
    row = cur.fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?);",
            (str(SCHEMA_VERSION),),
        )
    conn.commit()


def get_existing_card_ids(conn: sqlite3.Connection) -> set[int]:
    cur = conn.execute("SELECT card_id FROM cards;")
    return {int(r["card_id"]) for r in cur.fetchall()}


@dataclass(frozen=True)
class Skill:
    idx: int
    kind: str | None
    name: str | None
    cost: list[str]
    damage: str | None
    effect: str | None
    effect_text_norm: str | None = None
    instructions: list[str] | None = None

    def to_row(self, card_id: int) -> dict[str, Any]:
        instructions_json = None
        if self.instructions is not None:
            instructions_json = json.dumps(self.instructions, ensure_ascii=False)
        return {
            "card_id": card_id,
            "idx": self.idx,
            "kind": self.kind,
            "name": self.name,
            "cost_json": json.dumps(self.cost, ensure_ascii=False),
            "damage": self.damage,
            "effect": self.effect,
            "effect_text_norm": self.effect_text_norm,
            "instructions_json": instructions_json,
        }


def upsert_card(
    conn: sqlite3.Connection,
    *,
    card_id: int,
    card: dict[str, Any],
    skills: Iterable[Skill],
) -> None:
    payload_json = json.dumps(card, ensure_ascii=False, separators=(",", ":"))
    fetched_at = card.get("fetched_at") or _utc_now_iso()

    card_row = {
        "card_id": card_id,
        "name": card.get("name") or "",
        "evolve_marker": card.get("evolve_marker"),
        "card_type": card.get("card_type"),
        "hp": card.get("hp"),
        "element_code": card.get("element_code"),
        "element": card.get("element"),
        "regulation_mark": card.get("regulation_mark"),
        "collector_number": card.get("collector_number"),
        "expansion_code": card.get("expansion_code"),
        "expansion_name": card.get("expansion_name"),
        "expansion_symbol_url": card.get("expansion_symbol_url"),
        "illustrator": card.get("illustrator"),
        "image_url": card.get("image_url"),
        "weakness_code": card.get("weakness_code"),
        "weakness_value": card.get("weakness_value"),
        "resistance_code": card.get("resistance_code"),
        "resistance_value": card.get("resistance_value"),
        "retreat_cost": card.get("retreat_cost"),
        "pokedex_no": card.get("pokedex_no"),
        "height_m": card.get("height_m"),
        "weight_kg": card.get("weight_kg"),
        "description": card.get("description"),
        "source_url": card.get("source_url") or "",
        "fetched_at": fetched_at,
        "raw_json": payload_json,
    }

    with conn:
        conn.execute(
            """
            INSERT INTO cards(
                card_id, name, evolve_marker, card_type, hp, element_code, element,
                regulation_mark, collector_number, expansion_code, expansion_name,
                expansion_symbol_url, illustrator, image_url,
                weakness_code, weakness_value, resistance_code, resistance_value, retreat_cost,
                pokedex_no, height_m, weight_kg, description,
                source_url, fetched_at, raw_json
            ) VALUES (
                :card_id, :name, :evolve_marker, :card_type, :hp, :element_code, :element,
                :regulation_mark, :collector_number, :expansion_code, :expansion_name,
                :expansion_symbol_url, :illustrator, :image_url,
                :weakness_code, :weakness_value, :resistance_code, :resistance_value, :retreat_cost,
                :pokedex_no, :height_m, :weight_kg, :description,
                :source_url, :fetched_at, :raw_json
            )
            ON CONFLICT(card_id) DO UPDATE SET
                name=excluded.name,
                evolve_marker=excluded.evolve_marker,
                card_type=excluded.card_type,
                hp=excluded.hp,
                element_code=excluded.element_code,
                element=excluded.element,
                regulation_mark=excluded.regulation_mark,
                collector_number=excluded.collector_number,
                expansion_code=excluded.expansion_code,
                expansion_name=excluded.expansion_name,
                expansion_symbol_url=excluded.expansion_symbol_url,
                illustrator=excluded.illustrator,
                image_url=excluded.image_url,
                weakness_code=excluded.weakness_code,
                weakness_value=excluded.weakness_value,
                resistance_code=excluded.resistance_code,
                resistance_value=excluded.resistance_value,
                retreat_cost=excluded.retreat_cost,
                pokedex_no=excluded.pokedex_no,
                height_m=excluded.height_m,
                weight_kg=excluded.weight_kg,
                description=excluded.description,
                source_url=excluded.source_url,
                fetched_at=excluded.fetched_at,
                raw_json=excluded.raw_json
            ;
            """,
            card_row,
        )

        conn.execute("DELETE FROM skills WHERE card_id = ?;", (card_id,))
        conn.executemany(
            """
            INSERT INTO skills(card_id, idx, kind, name, cost_json, damage, effect, effect_text_norm, instructions_json)
            VALUES (:card_id, :idx, :kind, :name, :cost_json, :damage, :effect, :effect_text_norm, :instructions_json);
            """,
            [s.to_row(card_id) for s in skills],
        )


def copy_cards_from_db(
    src_conn: sqlite3.Connection,
    dst_conn: sqlite3.Connection,
    *,
    regulation_marks: set[str] | None = None,
) -> int:
    """
    Copy cards (and their skills) from src_conn to dst_conn.
    If regulation_marks is specified, only copy cards matching those marks.
    Returns number of cards copied.
    """
    init_db(dst_conn)

    where_clause = ""
    params: tuple = ()
    if regulation_marks:
        placeholders = ",".join("?" for _ in regulation_marks)
        where_clause = f"WHERE UPPER(regulation_mark) IN ({placeholders})"
        params = tuple(m.upper() for m in regulation_marks)

    cards = src_conn.execute(
        f"SELECT * FROM cards {where_clause};", params
    ).fetchall()

    copied = 0
    for card_row in cards:
        card_id = card_row["card_id"]
        card_dict = dict(card_row)
        
        # Get skills for this card
        skills_rows = src_conn.execute(
            "SELECT * FROM skills WHERE card_id = ? ORDER BY idx;", (card_id,)
        ).fetchall()
        
        skills = []
        for s in skills_rows:
            s_dict = dict(s)
            skills.append(
                Skill(
                    idx=s_dict["idx"],
                    kind=s_dict.get("kind"),
                    name=s_dict.get("name"),
                    cost=json.loads(s_dict.get("cost_json") or "[]"),
                    damage=s_dict.get("damage"),
                    effect=s_dict.get("effect"),
                    effect_text_norm=s_dict.get("effect_text_norm"),
                    instructions=json.loads(s_dict["instructions_json"]) if s_dict.get("instructions_json") else None,
                )
            )
        
        # Upsert into destination
        upsert_card(dst_conn, card_id=card_id, card=card_dict, skills=skills)
        copied += 1

    dst_conn.commit()
    return copied
