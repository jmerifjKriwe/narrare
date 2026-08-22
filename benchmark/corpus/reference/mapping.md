# Reference Mapping — F-Ids to Representations

Durable, repo-committed mapping from story-bible fact ids (F001, F002, …) to
their reference representations in `entities.yaml` / `relations.yaml` /
`events.yaml`. Per schema, F-ids exist only on entity fact rows; relations and
events carry no F-id field, so their fact anchoring is documented here. This
file is the completeness substrate for the reference validation pass and for
later benchmark scoring. Rows consolidate the reference-batch task reports,
including their fix rounds.

Notation: `anna-fact` = fact row with that F-id on `p_anna_meyer` in
`entities.yaml` (analogously `<entity>-fact`); `Rxxx` / `Exxx` = relation /
event in `relations.yaml` / `events.yaml`; `PFxxx` / `OFxxx` = place / object
fact row. `+` joins dual representations of one source fact (an entity-fact
attribute and a relation/event/place-fact encoding coexist by design).

## NO-REP criterion

A fact gets no reference representation (`NO-REP`) iff it is narrative texture,
meta-narrative evaluation, or an in-world absence with no assertable triple —
NOT merely because it is a scene beat. Dateable scene beats ARE events, cf.
E002/E006/E014/E015. NO-REP is a coverage class, not a gap.

RETIRED class = F088 (retired in bible fix round, never planted).

Convention: profession facts anchor to the dated decision/acceptance where that is what the prose dates (F074: acceptance 2021-03; the work start autumn 2021 is scene texture), and to the actual start otherwise (F089: 2021-09).

## Chapters 1-3 (F001-F032)

| F-id | Representation(s) |
|------|-------------------|
| F001 | E001 |
| F002 | E001 |
| F003 | E002 |
| F004 | anna-fact |
| F005 | anna-fact |
| F006 | anna-fact + PF001 |
| F007 | R001 |
| F008 | thomas-fact |
| F009 | peter-fact |
| F010 | peter-fact |
| F011 | thomas-fact |
| F012 | E003 |
| F013 | lisa-fact |
| F014 | lisa-fact |
| F015 | R006 |
| F016 | lisa-fact |
| F017 | thomas-fact |
| F018 | peter-fact + E004 |
| F019 | E005 |
| F020 | E006 |
| F021 | anna-fact |
| F022 | anna-fact + PF002 + PF003 |
| F023 | marco-fact + R003 |
| F024 | martin-fact + R004 |
| F025 | R005 |
| F026 | hajo-fact |
| F027 | lisa-fact + E007 |
| F028 | E008 |
| F029 | R002 + E008 |
| F030 | R007 |
| F031 | anna-fact |
| F032 | peter-fact |

## Chapters 4-6 (F033-F065)

| F-id | Representation(s) |
|------|-------------------|
| F033 | E009 |
| F034 | anna-fact |
| F035 | peter-fact |
| F036 | margarete-fact |
| F037 | R008 |
| F038 | PF004 + PF005 |
| F039 | R009 |
| F040 | R010 |
| F041 | E014 |
| F042 | R012 |
| F043 | ilse-fact |
| F044 | gert-fact |
| F045 | E010 |
| F046 | margarete-fact |
| F047 | R011 |
| F048 | OF001 + E011 |
| F049 | OF003 |
| F050 | margarete-fact |
| F051 | OF002 |
| F052 | NO-REP (absence-of-suspicion texture) |
| F053 | margarete-fact |
| F054 | juna-fact + E012 |
| F055 | R013 |
| F056 | R014 |
| F057 | anna-fact |
| F058 | peter-fact |
| F059 | juna-fact |
| F060 | R015 + R016 |
| F061 | OF005 + E013 |
| F062 | OF004 |
| F063 | NO-REP (partial-reveal texture) |
| F064 | E015 |
| F065 | NO-REP (in-world absence: no second letter bundle) |

## Chapters 7-9 (F066-F099 + F135)

| F-id | Representation(s) |
|------|-------------------|
| F066 | OF006 + E016 |
| F067 | gert-profession-to + E017 |
| F068 | gert profession fact |
| F069 | gert age fact |
| F070 | PF009 |
| F071 | R017 + E018 |
| F072 | NO-REP (meta-narrative foreword) |
| F073 | NO-REP (negative: unconfirmed) |
| F074 | peter profession + E019 |
| F075 | OF008 + E020 |
| F076 | OF007 |
| F077 | ilse-profession-to + E021 |
| F078 | ilse age fact |
| F079 | E022 + PF006 |
| F080 | PF006 |
| F081 | PF007 |
| F082 | PF008 |
| F083 | PF001-valid_to + E022 |
| F084 | anna age fact |
| F085 | juna age fact |
| F086 | OF008 |
| F135 | OF002-valid_to + OF010 |
| F087 | NO-REP (residence summarizing, covered by intervals) |
| F089 | anna profession fact |
| F090 | anna profession valid_to (dual) |
| F091 | R018 |
| F092 | R018 (dual) |
| F093 | maria profession fact |
| F094 | E024 |
| F095 | R019 |
| F096 | anna_meier residence fact |
| F097 | NO-REP (texture) |
| F098 | OF009 |
| F099 | NO-REP (negative: unconfirmed) |

Note: F022 closed 2021-08 and F009 closed 2021-03 by predecessor-closure convention (cast intervals 2017–2021 / 2013–2021).

---

This file is extended per reference batch (chapters 7+ append a new section;
existing rows are only corrected, never silently dropped). The Task-11
completeness diff: every F-id from F001 upward appears exactly once in some
table above with either a representation or the NO-REP class.
