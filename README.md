# [1.13] BPM / Laws+ Compatch

Compatibility patch between **Better Politics Mod** (workshop `2932134122`) and
**Laws +** (workshop `2941539986`) for Victoria 3 **1.13**.

## Load order

```
Better Politics Mod
Laws +
[1.13] BPM / Laws+ Compatch      <- last
```

Every file uses the `zzzzzzzzzz_` prefix so it wins the ASCII filename ordering the
game uses to resolve entries defined by more than one mod. That ordering takes
precedence over the mod list, so the patch works from any position, but keeping it
last is still recommended. If another mod in your set uses an even longer run of
`z` characters, `python tools/build.py --check` will report it.

## Design rule

Better Politics Mod is the systemic mod: it rebuilds voting, interest groups and
institutions. Laws+ is a content mod: it adds laws. Wherever the two disagree, the
patch keeps the mechanics and the scale of Better Politics Mod and adapts the Laws+
content to them.

## What the patch does

| File | Contents |
|---|---|
| `common/ideologies/…_ideologies.txt` | Better Politics Mod ideologies gain a stance on the 35 laws Laws+ adds |
| `common/ideologies/…_lawsplus_ideologies.txt` | the three Laws+ ideologies gain a stance on Better Politics Mod laws |
| `common/laws/…_laws.txt` | Better Politics Mod laws wired to the ballot and discrimination law groups from Laws+ |
| `common/laws/…_lawsplus_laws.txt` | Laws+ laws given `country_rigidity_baseline_add` and the economy institution binding |
| `common/scripted_triggers/…` | Better Politics Mod leader classifiers recognise the Laws+ ideologies |
| `common/scripted_effects/…` | election shutdown, law categories, communism and populism trackers |
| `common/government_types/…` | council and soviet governments recognise Laws+ laws |
| `common/amendments/…` | electoral and socialisation amendments |
| `common/political_movements/…` | movements accept leaders holding Laws+ ideologies |
| `common/interest_groups/…` | attraction weights for `law_meritocratic_bureaucracy` and `law_gwageo` |

Ideology stances carry a tag: `# laws+` for values written by Laws+ that a full
override would otherwise discard, `# bpm` for values taken from Better Politics Mod,
`# derived` for values worked out from the ideology's stance on the closest
counterpart law or interpolated by `progressiveness` within the same law group.
Hand edits to any of them survive a rebuild.

## Deliberate omissions

* Laws+ law enactment events are not restored; Better Politics Mod replaces random
  legislative events with its own enactment system.
* Laws+ flavour (party weights, party names, interest group weights) is not carried
  over where Better Politics Mod rewrote the system.
* `law_multicultural` is skipped: Better Politics Mod injects an `is_visible` block
  into a law Laws+ defines in full, so that injection is already discarded by the
  game before this patch loads.

## Rebuilding

The patch is generated. After either source mod updates:

```sh
python tools/build.py
```

The script locates the game and the workshop automatically, regenerates every file
under `common/`, and validates the result. `--check` validates without rebuilding;
`--game DIR --workshop DIR` overrides the search.

Validation covers brace balance, whether every entry still wins the load order and
every `REPLACE:`/`INJECT:` has a target, whether anything the source mods define was
dropped, and whether any law, ideology, movement or law group reference is unresolved.

## Override modes

The game handles a repeated block inside one entry in two different ways, and the
patch picks its mode accordingly:

| Section | Behaviour | Mode used |
|---|---|---|
| effects and triggers (`on_activate`, `is_visible`, `ai_will_do`, `possible`, …) | the second block is discarded | `REPLACE:` of the whole entry |
| modifiers and lists (`modifier`, `disallowing_laws`, `allowed_laws`, …) | blocks are summed or concatenated | `INJECT:` carrying only the added lines |
