# FIND-019: Consistency-Check — keine "Ignorieren"/"Resolved"-Markierung für Befunde
Priorität: 🟡 Mittel
Status: Offen
Review: cr-07
CR-AUFG: CR-AUFG-07-26

## Befund

`ConsistencyCheckPanel` / `ConsistencyResults` haben keinen Mechanismus, einen
Befund als "ignorieren" oder "bewusst akzeptiert" zu markieren. Bei jedem
Re-Run (`handleRunCheck`) erscheinen alle Issues erneut — auch solche, die der
Nutzer bereits bewusst entschieden hat.

Für wiederholte Consistency-Checks im Schreibprozess ist das frustrierend
(Noise vs. Signal).

## Evidenz

- `packages/web/.../ConsistencyCheckPanel.tsx:67-69` — `handleRunCheck` lädt
  alle Issues neu.
- `packages/web/.../ConsistencyResults.tsx` — kein Dismiss/Ignore-Mechanismus.
- `ConsistencyCard` (`WorldbuildingAnalysisCards.tsx:124-181`) — hat
  Severity-Badges, Entity-Links, Confidence, aber keinen Dismiss-Button.
- Kein Backend-Endpoint für Dismiss/Resolve gefunden.

## Auswirkung

Wiederholte Konsistenz-Checks zeigen gelöste/akzeptierte Issues immer wieder
an. Der Nutzer muss mental filtern, was er schon bewertet hat. Bei fortlaufendem
Schreibprozess mit regelmäßigen Checks entsteht "Issue-Fatigue" — der Nutzer
ignoriiert irgendwann alle Befunde, auch neue wichtige.

## Empfehlung

- **Backend:** `POST /api/v1/novels/{id}/consistency/issues/{finding_index}/dismiss`
  mit `reason`-Feld (persistiert in DB, novel-scoped).
- **Frontend:** `ConsistencyCard` erhält einen "Ignorieren"-Button (IconButton
  mit `OctagonX`-Icon), der den API-Call auslöst und die Card ausblendet /
  als "dismissed" markiert.
- `ConsistencyCheckResponse` erhält ein `dismissed_findings: number[]`-Feld;
  `ConsistencyResults` filtert diese heraus (mit Toggle "Ausgeblendete zeigen").
- URL-Param `?showDismissed=1` für Transparenz.

**Owner:** Backend + Frontend.

## Verifikation

- [ ] Backend-Endpoint für Dismiss existiert (DB-persistiert)
- [ ] Dismissed-Issues erscheinen nicht mehr im Default-View
- [ ] Toggle zeigt sie wieder (mit dismissed-Badge)
- [ ] Persistenz über Sessions hinweg (DB-backed)
