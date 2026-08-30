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

Nazwy wszystkich plików mają prefiks `zzzzzzzzzz_`, więc wygrywają sortowanie ASCII, którym
Victoria 3 rozstrzyga konflikty między różnie nazwanymi plikami. Dzięki temu patch działa
niezależnie od pozycji na liście — ale trzymanie go na końcu i tak jest zalecane.

## Co robi patch

| Plik | Zakres |
|---|---|
| `common/ideologies/zzzzzzzzzz_compat_ideologies.txt` | 132 ideologie BPM dostają stanowiska wobec 35 praw dodanych przez Laws+ |
| `common/ideologies/zzzzzzzzzz_compat_lawsplus_ideologies.txt` | 3 ideologie własne Laws+ (`anarcho_liberal`, `clerical_fascist`, `national_socialist`) dostają stanowiska wobec praw BPM |
| `common/laws/zzzzzzzzzz_compat_laws.txt` | sprzężenie praw BPM z `lawgroup_ballot_system`, `law_corporatocracy`, `law_proletariat_dictatorship`, `law_cosmopolitanism` |
| `common/scripted_triggers/zzzzzzzzzz_compat_triggers.txt` | klasyfikatory przywódców BPM rozpoznają ideologie Laws+ (to naprawia też partie, agendy AI i wiele systemów BPM naraz) |
| `common/scripted_effects/zzzzzzzzzz_compat_effects.txt` | wyłączanie wyborów, kategoria praw ustrojowych, wskaźniki komunizmu/populizmu |
| `common/government_types/zzzzzzzzzz_compat_government_types.txt` | ustroje radzieckie/sowieckie i faszystowskie rozpoznają prawa Laws+ |
| `common/amendments/zzzzzzzzzz_compat_amendments.txt` | poprawki wyborcze i socjalizacyjne |
| `common/political_movements/zzzzzzzzzz_compat_political_movements.txt` | ruchy polityczne przyjmują przywódców o ideologiach z Laws+ |
| `common/interest_groups/zzzzzzzzzz_compat_interest_groups.txt` | wagi poparcia dla `law_meritocratic_bureaucracy` i `law_gwageo` |
| `common/laws/zzzzzzzzzz_compat_lawsplus_laws.txt` | prawa Laws+ przeniesione na model BPM: `country_rigidity_baseline_add` oraz `institution`/`institution_modifier` |

## Regeneracja po aktualizacji modów źródłowych

Patch jest **generowany**, nie pisany ręcznie. Po aktualizacji BPM lub Laws+ wystarczy:

```sh
python tools/merge_ideo.py     # ideologie BPM  (czyta stanowiska z istniejącego pliku)
python tools/gen_ideo_gaps.py  # uzupełnienie luk regułami (analogia / interpolacja)
python tools/gen_laws.py       # prawa BPM
python tools/gen_lp_laws.py    # prawa Laws+ na modelu BPM (rigidity, instytucje)
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


## Patch jest budowany pod konkretny zestaw modów

Generatory nie patrzą na surowe definicje z BPM, tylko na **definicję efektywną** — czyli tę,
którą gra faktycznie załaduje po rozstrzygnięciu wszystkich modów z `content_load.json`
(`tools/playset.py`). Bez tego patch po cichu cofałby zmiany modów sortujących się później:
w tym zestawie 22 ideologie przywódców przepisuje „BPM + Tech & Res ComPatch", a kilka praw
i ruchów — Community Mod Framework oraz Kuromi's AI.

Konsekwencja: **plik wynikowy zawiera treść także tych modów.** Patch jest przez to
dopasowany do bieżącego zestawu, a nie uniwersalny. Po zmianie listy modów trzeba go
przegenerować. Do publikacji na Workshopie trzeba by albo dopisać te mody jako zależności,
albo przegenerować patch na czystym zestawie BPM + Laws+.

## Zasada projektowa

**BPM wyznacza model, Laws+ się do niego dopasowuje.** BPM przebudowuje system głosowania,
frakcje polityczne i instytucje; Laws+ dokłada prawa. Wszędzie, gdzie oba mody mówią co innego,
obowiązuje mechanika i skala BPM, a prawa Laws+ są do niej doginane — nigdy odwrotnie.

Konsekwencje widoczne w plikach:

* prawa Laws+ dostają `country_rigidity_baseline_add` w skali BPM (odniesienia do konkretnych
  praw BPM są w komentarzach w `tools/gen_lp_laws.py`);
* prawa Laws+ z `lawgroup_economic_system` dostają `institution_economy`, bo BPM wiąże
  instytucję z całą tą grupą;
* `lawgroup_ballot_system` (nowa grupa Laws+) jest podpięty pod ustroje BPM — ustrój bez
  legislatywy wyłącza wybory, powrót do głosowania przywraca kartę wyborczą;
* ideologie Laws+ dostają stanowiska wobec praw BPM, a nie odwrotnie;
* eventy uchwalania praw z Laws+ **nie** są przywracane, bo BPM celowo zastępuje losowe
  wydarzenia legislacyjne własną minigrą;
* flavour Laws+ (wagi partii, nazwy partii, wagi IG) nie jest przenoszony tam, gdzie BPM
  przepisał dany system od zera.

Stanowiska ideologii oznaczone `# auto` w `zzzzzzzzzz_compat_ideologies.txt` są wyprowadzone
regułami; można je ręcznie poprawiać — generator zachowa każdą ręczną zmianę.
