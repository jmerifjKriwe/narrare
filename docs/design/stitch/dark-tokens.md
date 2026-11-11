# Dark tokens — Midnight Ink, from the S0 Stitch round
The dark half of the norm, answered by the 2026-11-11 Stitch round (plan task S0).
Sources: the token reference card [`documents/midnight-ink-swatches.html`](documents/midnight-ink-swatches.html)
(`eecacfd51e574e7e899d5ccecc43c07d`) for the gap values DESIGN.md does not name, and the
dark shelf [`screens/library/shelf-dark.html`](screens/library/shelf-dark.html)
(`29f14b8ff1cf451398beb12503b53716`) as the rendered composition. Contrasts below are
measured here (WCAG relative luminance), not copied.

## Area hues (gap G-1)
Dark counterpart of each light hue; measured on panel `#1C1914` (the rail's ground) and card `#211F1A`.

| Token | Dark | Light basis | vs `#1C1914` | vs `#211F1A` |
|---|---|---|---|---|
| `--area-writing` | `#D88D68` | `#914F2F` | 6.62:1 | 6.22:1 |
| `--area-knowledge` | `#B4B65B` | `#606127` | 8.16:1 | 7.67:1 |
| `--area-chat` | `#72A5C3` | `#3A637B` | 6.58:1 | 6.18:1 |
| `--area-planning` | `#C686C0` | `#834D7E` | 6.32:1 | 5.94:1 |
| `--area-settings` | `#ABA391` | `#5A5549` | 6.99:1 | 6.57:1 |

## State colours (gap G-1)
Text on card ground `#211F1A`; container and border as the card's own pill triple.

| Token | Text | Container | Border | Text vs `#211F1A` | Text vs container |
|---|---|---|---|---|---|
| `--state-success` | `#52D47E` | `#172D1E` | `#274830` | 8.68:1 | 7.74:1 |
| `--state-warning` | `#E5A84B` | `#302111` | `#523817` | 7.87:1 | 7.43:1 |
| `--state-danger` | `#F27474` | `#331515` | `#522222` | 5.9:1 | 5.98:1 |

## Primary and focus in dark (gap G-3)

| Pair | Values | Measured |
|---|---|---|
| primary fill / its text | `#D39562` / `#1D140D` | 7.12:1 |
| primary fill on canvas | `#D39562` on `#16140F` | 7.23:1 |
| focus ring on panel | `#F2AD73` on `#1C1914` | 9.18:1 |

## Surfaces and text (DESIGN.md wins)

DESIGN.md already names these; the round's screens agree except where noted:
`--background #16140F` · `--panel #1C1914` · `--card #211F1A` · `--soft #2C2922` ·
`--border #35332D` · `--rule #302D28` · `--foreground #DFDEDA` · `--muted #89867F`.

## Divergences inside the round (logged)

The two generated screens disagree on some values; the ruling below fixes the norm.

| Role | Token card | Dark shelf rendering | Binding |
|---|---|---|---|
| area hues | `#D88D68` `#B4B65B` `#72A5C3` `#C686C0` `#ABA391` | `#E28659` `#64B5F6` `#C37DBE` (others unlabelled) | **card** — named, measured, light bases match DESIGN.md exactly |
| state colours | `#52D47E` `#E5A84B` `#F27474` | `#66BB6A` `#FFB74D` (no danger) | **card** |
| foreground | card shows `#EDE7DE` as its text grey | `#DFDEDA` | **`#DFDEDA`** — DESIGN.md names it |

*Ruling (coordinator, 2026-11-11): where DESIGN.md names a dark value it is binding; where
it does not, the token card fills the gap; the dark shelf is the composition reference for
Task 12's side-by-side, whose dark leg may therefore show accent hue deltas until the card
values are re-rendered. If the owner prefers the shelf's renderings as the norm, one edit
round on the card settles it.*

## Surface ladder and the remaining pairs (gap closed 2026-11-11)

From the second S0 card [`documents/midnight-ink-surface-ladder.html`](documents/midnight-ink-surface-ladder.html)
(`02ac2aa7825f4faeb76e353a7fad2b9d`), measured here:

| Token | Dark | Note | Measured |
|---|---|---|---|
| `--surface-container-lowest` | `#100E0A` | deepest step (-6) |  |
| `--surface-container-low` | `#191611` | -2 |  |
| `--surface-container` | `#211F1A` | 0 — equals `--card` |  |
| `--surface-container-high` | `#27241E` | +2 |  |
| `--surface-container-highest` | `#2E2A23` | +4 |  |
| `--surface-variant` | `#3A352C` | +6 |  |
| `--outline` | `#564E43` | hairline precision | 2.25:1 vs canvas |
| `--outline-variant` | `#3D372E` | subtle hairline / rules | 1.56:1 vs canvas |
| `--secondary` | `#D7A892` | warm terracotta-rose fill | 7.29:1 with on-secondary |
| `--on-secondary` | `#3B1C10` |  |  |
| `--secondary-container` | `#47291D` | muted leather brown | 9.91:1 with on-secondary-container |
| `--on-secondary-container` | `#FED8CA` |  |  |
| `--inverse-surface` | `#EDE0D4` | inverse pair is light in dark mode | 12.71:1 with on-inverse-surface |
| `--on-inverse-surface` | `#211F1A` |  |  |
| `--inverse-primary` | `#743B1F` | the light primary on inverse ground | 6.79:1 vs inverse-surface |

Light counterparts remain DESIGN.md's named values (screen-wins applies per §6.2).
