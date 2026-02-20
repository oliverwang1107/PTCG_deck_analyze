import sqlite3

# JP Database
jp_conn = sqlite3.connect('data/ptcg_jp.sqlite')
print('=== JP Database Statistics ===')
total = jp_conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
print(f'Total cards: {total}')

print('\nTop 20 expansions:')
for row in jp_conn.execute('SELECT expansion_code, COUNT(*) cnt FROM cards GROUP BY expansion_code ORDER BY cnt DESC LIMIT 20').fetchall():
    print(f'  {row[0]}: {row[1]} cards')

print('\nRegulation marks:')
for row in jp_conn.execute('SELECT regulation_mark, COUNT(*) cnt FROM cards GROUP BY regulation_mark ORDER BY cnt DESC').fetchall():
    mark = row[0] if row[0] else '(null)'
    print(f'  {mark}: {row[1]} cards')

# TW Database
tw_conn = sqlite3.connect('data/ptcg_hij.sqlite')
print('\n=== TW Database (HIJ only) ===')
hij_count = tw_conn.execute('SELECT COUNT(*) FROM cards WHERE regulation_mark IN (?,?,?)', ('H','I','J')).fetchone()[0]
print(f'Total HIJ cards: {hij_count}')

tw_exp = set([r[0] for r in tw_conn.execute('SELECT DISTINCT expansion_code FROM cards WHERE regulation_mark IN (?,?,?)', ('H','I','J')).fetchall()])
jp_exp = set([r[0] for r in jp_conn.execute('SELECT DISTINCT expansion_code FROM cards').fetchall()])
common = tw_exp.intersection(jp_exp)

print(f'\nTW expansions (HIJ): {len(tw_exp)}')
print(f'JP expansions: {len(jp_exp)}')
print(f'Common expansions: {len(common)} ({len(common)/len(tw_exp)*100:.1f}% coverage)')

missing = tw_exp - jp_exp
if missing:
    print(f'\nMissing in JP ({len(missing)}):')
    for exp in sorted(missing):
        count = tw_conn.execute('SELECT COUNT(*) FROM cards WHERE expansion_code = ? AND regulation_mark IN (?,?,?)', (exp, 'H','I','J')).fetchone()[0]
        print(f'  {exp}: {count} cards')

extra = jp_exp - tw_exp
print(f'\nExtra in JP (possibly non-HIJ): {len(extra)} expansion codes')
