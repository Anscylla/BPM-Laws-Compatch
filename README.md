# [1.13] BPM / Laws+ Compatch

Patch zgodności między **Better Politics Mod** (workshop `2932134122`, v2.5) a **Laws +**
(workshop `2941539986`, v1.12.12) pod Victoria 3 **1.13**.

Zastępuje nieaktualizowany od roku patch `3481491071`.

## Kolejność modów

```
Better Politics Mod
Laws +
[1.13] BPM / Laws+ Compatch      <- zawsze na końcu
```

Nazwy wszystkich plików mają prefiks `zzzzz_`, więc wygrywają sortowanie ASCII, którym
Victoria 3 rozstrzyga konflikty między różnie nazwanymi plikami. Dzięki temu patch działa
niezależnie od pozycji na liście — ale trzymanie go na końcu i tak jest zalecane.

## Co robi patch

| Plik | Zakres |
|---|---|
| `common/ideologies/zzzzz_compat_ideologies.txt` | 132 ideologie BPM dostają stanowiska wobec 35 praw dodanych przez Laws+ |
| `common/ideologies/zzzzz_compat_lawsplus_ideologies.txt` | 3 ideologie własne Laws+ (`anarcho_liberal`, `clerical_fascist`, `national_socialist`) dostają stanowiska wobec praw BPM |
| `common/laws/zzzzz_compat_laws.txt` | sprzężenie praw BPM z `lawgroup_ballot_system`, `law_corporatocracy`, `law_proletariat_dictatorship`, `law_cosmopolitanism` |
| `common/scripted_triggers/zzzzz_compat_triggers.txt` | klasyfikatory przywódców BPM rozpoznają ideologie Laws+ (to naprawia też partie, agendy AI i wiele systemów BPM naraz) |
| `common/scripted_effects/zzzzz_compat_effects.txt` | wyłączanie wyborów, kategoria praw ustrojowych, wskaźniki komunizmu/populizmu |
| `common/government_types/zzzzz_compat_government_types.txt` | ustroje radzieckie/sowieckie i faszystowskie rozpoznają prawa Laws+ |
| `common/amendments/zzzzz_compat_amendments.txt` | poprawki wyborcze i socjalizacyjne |
| `common/political_movements/zzzzz_compat_political_movements.txt` | ruchy polityczne przyjmują przywódców o ideologiach z Laws+ |
| `common/interest_groups/zzzzz_compat_interest_groups.txt` | wagi poparcia dla `law_meritocratic_bureaucracy` i `law_gwageo` |

## Regeneracja po aktualizacji modów źródłowych

Patch jest **generowany**, nie pisany ręcznie. Po aktualizacji BPM lub Laws+ wystarczy:

```sh
python tools/merge_ideo.py     # ideologie BPM  (czyta stanowiska z istniejącego pliku)
python tools/gen_laws.py       # prawa
python tools/gen_rest.py       # triggery, efekty, ustroje, poprawki, ruchy, IG
python tools/gen_lp_ideo.py    # ideologie Laws+
python tools/verify.py         # czy wpisy patcha wygrywają i czy REPLACE ma cel
python tools/dangling.py       # nierozwiązane referencje w całym stosie modów
python tools/brace.py common/*/*.txt
```

Skrypty w `tools/` mają zaszyte ścieżki do `C:\Steam\steamapps` — zmień je w `tools/conflicts.py`,
jeśli gra jest gdzie indziej. Folder `tools/` jest ignorowany przez grę.

Narzędzia diagnostyczne: `tools/lost.py` (co z Laws+ ginie pod BPM), `tools/ctx.py <katalog>`
(pokazuje konkretne linie z kontekstem bloków), `tools/show.py <katalog> <klucz>` (porównanie
definicji BPM vs Laws+).
