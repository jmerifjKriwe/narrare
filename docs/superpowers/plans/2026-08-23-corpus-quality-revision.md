# Corpus Quality Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise all 12 German benchmark chapters to the literary quality level PO-approved in the ch-01 pilot (scenes 1–2, 2026-08-23) while preserving every mechanical binding: facts checkable, registry anchors verbatim, word corridor, leakage discipline, cross-chapter texture.

**Architecture:** Per-chapter revision tasks in small scene-scoped dispatches (2–4 per chapter — one-shot chapter rewrites fail silently per package-2 evidence). Preservation constraints per chapter are extracted MECHANICALLY at task start (anchors via registry query), never from memory. Pilot defects list is the style baseline; each revision keeps dialogue register, rhythm variance, sensory anchors, pruned metaphors.

**Tech Stack:** Markdown prose, rg + `uv run python -c` registry queries for constraint extraction, standard repo hooks.

**Pilot (completed, uncommitted):** ch-01 scenes 1–2 revised and PO-approved ("qualitativ sehr viel besser"). T1 completes ch-01 and commits the full chapter revision.

## Global Constraints (binding for every task)

- STYLE BASELINE (from pilot): sentence-length variance (2–30 words; 3-word sentences allowed); verbs over nominalizations; dialogue carries scenes where people are present; ≤1 image/metaphor per paragraph, most paragraphs none; no interpretive narrator asides unless earned; varied paragraph lengths; quiet warm realism, gentle humor; concrete sensory anchors over abstraction.
- PRESERVATION (mechanically gated per task): (1) every F-fact of the chapter stays prose-checkable; (2) every registry anchor touching the chapter survives VERBATIM (`rg -F -c "<anchor>" <chapter>` = 1; anchors never move chapters); (3) word corridor 2,400–3,600 total per chapter (floor risk after trimming!); (4) no new proper names; (5) no later-chapter fact leakage, no removed facts either — the fact SET is frozen; (6) cross-chapter texture callbacks planted by this chapter stay (e.g. ch-01's zwanzig Stühle/Plastikbecher/Matthias beats); (7) one paragraph per line, `***` scene breaks, `#` title (improvable); (8) German prose, meta/report English.
- ANCHOR EXTRACTION (task start, verbatim): `uv run python -c "import yaml; [print(e['id'], e['chapter'], repr(e['anchor'])) for v in ['light','complex'] for e in yaml.safe_load(open(f'benchmark/corpus/variants/{v}/errors.yaml'))['errors']]"` → the task's chapter rows are the verbatim-survivor list.
- Registry files, reference YAMLs, mapping.md, bible are NEVER edited by revision tasks (only chapters). If a revision genuinely cannot preserve an anchor, STOP and escalate (coordinator decides re-anchoring with registry amendment).
- Reviews per task: preservation gates + reviewer spot-check (facts + style direction); quality ceiling = PO pilot standard; PO samples the end result.
- Per-task file cap: 1 chapter file per commit.

---

### Task 1: Complete ch-01 (scenes 3–4) + commit full revision
Pilot scenes 1–2 done. Extract anchors (expect L07). Revise scenes 3–4 (Elbe walk incl. the Kaimauer dialogue — already the best register, deepen it; closing scene) in 1–2 dispatches. Gates: corridor (watch the 2,437 floor — scenes 1–2 may give ~30 words if needed), L07 verbatim, Matthias beats + zwanzig Stühle + Plastikbecher intact, F001–F011 checkable, leakage sweep. Commit: whole-ch-01 revision (message documents pilot + completion).

### Task 2: ch-02 "Die richtigen Namen"
Wedding-meeting (F012–F017), move-in (F018), degree (F019–F021). Anchors: L08 (Lisa unacquaintance sentence — extract exact string). Texture: door-plate "Meyer, zweimal" (ch-03/04 deps), Schreibtisch arrival (ch-03 ¶25 antecedent), "sechs Wochen" rehearsal nuance (F027 fix history). Dialogue: the wedding table is a dialogue scene waiting to happen.

### Task 3: ch-03 "Noch ein Name"
Office world (F022–F032). Anchors: none (verify via extraction). Texture: Monatsbeginn (F022 fix), "seit Mitte Mai" freelance (F027 fix — exact phrase is load-bearing for the reference!), Weise/Wiese confusion mechanics (R005 + ch-04/07/09 callbacks), "seit dem Mai vor zwei Jahren" retrospect (E001 year derivation — load-bearing, preserve verbatim), Elbstrand proposal, ages ¶13.

### Task 4: ch-04 "Ein Tag im Mai"
Wedding (F033–F044). Anchors: L04 ("Der letzte Sonnabend im Mai" — extract). Texture: "siebzehn Tage zuvor, am neunten Mai" (L04 residual detection aid), Thomas toast + Elke correction (E014), Margarete oldest guest, vierzig Stühle vs ch-01's zwanzig (reviewer nit — make the relationship explicit or consistent: e.g. "doppelt so viele Stühle wie zur Lesung" resolves the 40-vs-20 cleanly), "Lieber Matthias" toast.

### Task 5: ch-05 "Das Genaue bleibt"
Death + estate (F045–F053). Anchors: X04 ("Der Zeichentisch ging an die Enkelin" — extract exact). Texture: inherit-vs-discover predicate distinction, "Seit 1980"-adjacent facts, drawer taped shut, Kellertreppe register (the good one), Zeichnerin 1948–1993. Tone: grief quiet, objects as memory.

### Task 6: ch-06 "Der Juni und der Oktober"
Birth + discovery (F054–F065). Anchors: L05 (birth sentence — extract). Texture: "seit Wochen gepackt" (fix history), Meldezettel first residence (F059), first bundle 1982–1984 + "dreizehn Briefe" count, Ilse deflection (E015, ch-10 seed), false-bottom discovery scene, NO second-bundle knowledge.

### Task 7: ch-07 "Der April, der Juli und der Dezember"
Frida/Gert/Sofia (F066–F073). Anchors: none expected. Texture: "sechste Skizzenbuch … Winter" (fix), Gert vierundsechzig + Vierzig Jahre/1980, jury scene LENZ badge (ch-08/10/11 callbacks), letters unconfirmed.

### Task 8: ch-08 "Was mitkommt und was bleibt"
The pivot (F074–F087, F135). Anchors: L03 ("Von diesem August an" — extract), L09 ("einundvierzig Jahre" — extract), X06 (piano sale sentence — extract). Texture: piano reveal (its ONLY chapter), "zwei Monate vor dem Umzug", "ein paar Wochen nach dem Einzug" decoupled arrival, Monatsbeginn-style job-acceptance "Ende März", Türkenstraße 41 arrival, table travels, humming leitmotif. Corridor watch: 2,943 current.

### Task 9: ch-09 "Gleichklang"
Munich + Maria + Anna Meier (F089–F099, F001-form2). Anchors: L10 ("im März 2015" — extract), X01 (Damals-sentence — contains L10's span; preserve the WHOLE anchor span verbatim), X02 (überhaupt-nicht-verwandt clause — extract). Texture: "viereinhalb Jahren" ×2 (fix history — load-bearing), "sechs Jahre Elbe" (distinct, keep), "seit diesem September" (R018 evidence), stairwell mix-up scene, sketchbooks unbroken.

### Task 10: ch-10 "Der zweite Bund"
The reveal (F100–F112). Anchors: none expected. Texture: "Du bist einunddreißig" (F111), "erst seit Monaten" (fix), einundvierzig conversions (fix sites), nameless son discipline (no name, no new facts), quarrel/reconciliation beats, practice DECISION only (no founding execution).

### Task 11: ch-11 "Der November und der Januar"
Surgery + founding (F113–F124, F137). Anchors: L02 (Gert age sentence — extract), X03 (Alexander paragraph — extract whole span), X08 (pen engraving — extract). Texture: "Siebenundsechzig"/"achtundsechzig" Nov-30 chain, LENZ badge return, card to the wrong Anna, Alex/Sascha split never resolved.

### Task 12: ch-12 "Was bleibt"
Closing (F125–F136, F134, restatements F001-form3/F051/F086-form2). Anchors: L01 (fünfunddreißig sentence — extract), L06 ("hier, in der Türkenstraße 41" — extract; X07's span is DISJOINT in the same passage — preserve BOTH spans verbatim, they sit in one sentence area), X07 (extract). Texture: "desselben Jahres" (fix), Ben "vom dritten Stock"/"seit 2022, also seit vier Jahren", watch promise (no transfer!), restatements genuinely restating in new prose — KEEP their content while improving around them.

### Task 13: Final sweep + CURRENT_STATE
Corpus-wide: all 18 anchors rg -F = 1 in named chapter; corridor ×12; leakage sweeps (klavier ch-08-only, etc.); fact spot-checks (10 random F-ids prose-derivable); wc totals. CURRENT_STATE: amend the package-2 entry (or one-line new entry) noting the quality revision pass. Commit.

---

## Plan Self-Review (executed)
- Coverage: 12 chapters + completion of pilot + final sweep ✓. Every registry anchor chapter covered (ch-01 L07; 02 L08; 04 L04+X05; 05 X04; 06 L05; 08 L03+L09+X06; 09 L10+X01+X02; 11 L02+X03+X08; 12 L01+L06+X07) ✓. Style baseline fixed from pilot ✓. Escalation path for impossible anchors ✓ (never silently re-anchor).
- Placeholder scan: texture notes are pointers to verified package-2 review facts, not TBDs; anchor strings are extracted mechanically per task (never hardcoded from memory) ✓.
- Type consistency: task order = chapter order; commit-per-chapter; registry/reference files untouchable ✓.
