"""Resolve the EFFECTIVE definition of a database entry across the whole active playset.

Victoria 3 resolves differently-named files by ASCII filename order (which beats the
mod-list position), and same-named files by mod-list position. A compatch that patches
the raw Better Politics Mod definition therefore silently discards whatever a
later-sorting third mod did to the same entry - in this playset that is
"Better Politics Mod + Tech & Res ComPatch", whose zzzzzzzzz_* files rewrite 22 BPM
leader ideologies.

`effective(dir, key)` replays that resolution and hands back the body the game would
actually end up with, so the generators can patch THAT instead.
"""
import os, re, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx
from conflicts import toplevel_keys, VAN

DOCS = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_LOAD = os.path.join(DOCS, 'content_load.json')

REPLACERS = ('', 'REPLACE', 'TRY_REPLACE', 'REPLACE_OR_CREATE')
INJECTORS = ('INJECT', 'TRY_INJECT', 'INJECT_OR_CREATE')


def roots():
    """[(label, path)] - vanilla first, then the enabled mods in load order.
    The compatch itself is excluded (we are the thing being generated)."""
    out = [('(vanilla)', VAN)]
    try:
        load = json.load(open(CONTENT_LOAD, encoding='utf-8-sig'))
    except Exception:
        return out
    for m in load.get('enabledMods', []):
        p = m['path']
        if os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(PROJ)):
            continue
        if os.path.isdir(p):
            out.append((os.path.basename(p.rstrip('\\/')), p))
    return out


_ROOTS = roots()


_VFS = {}


def _vfs(d):
    """filename -> (label, abspath), later mods shadowing same-named files."""
    if d in _VFS:
        return _VFS[d]
    out = {}
    for label, root in _ROOTS:
        base = os.path.join(root, *d.split('/'))
        if not os.path.isdir(base):
            continue
        for fn in os.listdir(base):
            if fn.endswith('.txt'):
                out[fn] = (label, os.path.join(base, fn))
    _VFS[d] = out
    return out


_INDEX = {}


def _index(d):
    """[(filename, label, {key: (mode, body)})] posortowane ASCII po nazwie pliku.
    Budowane raz na katalog - inaczej kazde zapytanie czytaloby kilkadziesiat plikow."""
    if d in _INDEX:
        return _INDEX[d]
    files = []
    for fn in sorted(_vfs(d)):
        label, path = _vfs(d)[fn]
        txt = pdx.read(path)
        entries = {}
        for k, mode in toplevel_keys(path):
            body = pdx.get_top(txt, k)
            if body is not None:
                entries[k] = (mode, body)
        files.append((fn, label, entries))
    _INDEX[d] = files
    return files


def _apply_inject(body, chunk):
    """Doklej wnetrze wstrzykiwanego wpisu. Sekcje o nazwie, ktora juz istnieje na
    poziomie 1, ZASTEPUJA istniejaca - tak dziala to w praktyce w silniku (BPM opiera
    na tym swoje INJECT-y, ktore np. odwracaja znak modyfikatorow z vanilli) i tak samo
    zachowa sie parser przy dwoch blokach o tej samej nazwie: liczy sie ostatni."""
    inner = chunk.split('\n')[1:-1]
    # rozbij wnetrze na sekcje najwyzszego poziomu wewnatrz wpisu
    secs, loose, depth, cur, acc = [], [], 0, None, []
    for line in inner:
        s = pdx.strip_c(line).strip()
        if depth == 0:
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{', s)
            if m:
                cur, acc = m.group(1), []
        if cur is not None:
            acc.append(line)
        else:
            loose.append(line)
        d0 = depth
        depth += pdx.strip_c(line).count('{') - pdx.strip_c(line).count('}')
        if cur is not None and d0 > 0 and depth == 0:
            secs.append((cur, acc)); cur = None
    for name, block in secs:
        r = pdx.find_sub(body, name)
        lines = body.split('\n')
        if r:
            lines[r[0]:r[1] + 1] = block
        else:
            lines[-1:-1] = block
        body = '\n'.join(lines)
    if loose:
        lines = body.split('\n')
        lines[-1:-1] = [l for l in loose if l.strip()]
        body = '\n'.join(lines)
    return body


_CACHE = {}


def effective(d, key):
    """-> (body, [(filename, label, mode), ...]) or (None, []).
    body has no mode prefix and is the definition the game ends up using."""
    ck = (d, key)
    if ck in _CACHE:
        return _CACHE[ck]
    body, trail = None, []
    for fn, label, entries in _index(d):
        if key not in entries:
            continue
        mode, chunk = entries[key]
        trail.append((fn, label, mode or 'definicja'))
        if mode in INJECTORS:
            if body is None:                      # INJECT_OR_CREATE bez celu
                body = chunk
            else:
                body = _apply_inject(body, chunk)
        else:
            body = chunk
    if body is not None:
        first = body.split('\n')[0].lstrip('\ufeff')
        for m in ('REPLACE_OR_CREATE:', 'TRY_REPLACE:', 'REPLACE:',
                  'INJECT_OR_CREATE:', 'TRY_INJECT:', 'INJECT:'):
            if first.startswith(m):
                first = first[len(m):]
                break
        body = '\n'.join([first] + body.split('\n')[1:])
    _CACHE[ck] = (body, trail)
    return _CACHE[ck]


def find(d, key):
    """Drop-in for the generators: -> (source description, body)."""
    body, trail = effective(d, key)
    if body is None:
        return None, None
    src = ' -> '.join(f'{lab}/{fn}' for fn, lab, _ in trail)
    return src, body


if __name__ == '__main__':
    print(f'Zrodla w kolejnosci ladowania: {len(_ROOTS)}')
    for d, k in (('common/ideologies', 'ideology_fascist'),
                 ('common/laws', 'law_agrarianism'),
                 ('common/laws', 'law_autocracy'),
                 ('common/political_movements', 'movement_fascist')):
        body, trail = effective(d, k)
        print(f'\n### {d}/{k}')
        for fn, lab, mode in trail:
            print(f'    {mode:<20} {lab}/{fn}')
