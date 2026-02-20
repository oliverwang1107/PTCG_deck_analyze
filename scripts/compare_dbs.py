import sqlite3

tw = sqlite3.connect('data/ptcg_hij.sqlite')
jp = sqlite3.connect('data/ptcg_jp.sqlite')

# Basic counts
tw_total = tw.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
jp_total = jp.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
print(f"=== TW DB (ptcg_hij.sqlite) ===")
print(f"Total cards: {tw_total}")

tw_hij = tw.execute("SELECT COUNT(*) FROM cards WHERE regulation_mark IN ('H','I','J')").fetchone()[0]
print(f"HIJ cards: {tw_hij}")

print(f"\n=== JP DB (ptcg_jp.sqlite) ===")
print(f"Total cards: {jp_total}")

# Compare by expansion_code + collector_number
tw_cards = set(tw.execute("SELECT expansion_code, collector_number FROM cards WHERE regulation_mark IN ('H','I','J')").fetchall())
jp_cards = set(jp.execute("SELECT expansion_code, collector_number FROM cards").fetchall())

both = tw_cards & jp_cards
tw_only = tw_cards - jp_cards

print(f"\n=== Comparison (expansion_code + collector_number) ===")
print(f"TW HIJ unique cards: {len(tw_cards)}")
print(f"JP unique cards: {len(jp_cards)}")
print(f"In both: {len(both)}")
print(f"TW only (missing in JP): {len(tw_only)}")
print(f"Coverage: {len(both)/len(tw_cards)*100:.1f}%")

if tw_only:
    print(f"\n=== Cards missing in JP (first 50) ===")
    for exp, num in sorted(tw_only)[:50]:
        row = tw.execute("SELECT name FROM cards WHERE expansion_code=? AND collector_number=?", (exp, num)).fetchone()
        name = row[0] if row else "?"
        print(f"  {exp}/{num}: {name}")
    if len(tw_only) > 50:
        print(f"  ... and {len(tw_only) - 50} more")

# Per-expansion comparison
print(f"\n=== Per-expansion coverage ===")
tw_exps = [r[0] for r in tw.execute("SELECT DISTINCT expansion_code FROM cards WHERE regulation_mark IN ('H','I','J') ORDER BY expansion_code").fetchall()]
for exp in tw_exps:
    tw_cnt = tw.execute("SELECT COUNT(*) FROM cards WHERE expansion_code=? AND regulation_mark IN ('H','I','J')", (exp,)).fetchone()[0]
    jp_cnt = jp.execute("SELECT COUNT(*) FROM cards WHERE expansion_code=?", (exp,)).fetchone()[0]
    if jp_cnt >= tw_cnt:
        status = "OK"
    else:
        status = f"MISSING {tw_cnt - jp_cnt}"
    print(f"  {exp}: TW={tw_cnt}, JP={jp_cnt} [{status}]")

tw.close()
jp.close()
