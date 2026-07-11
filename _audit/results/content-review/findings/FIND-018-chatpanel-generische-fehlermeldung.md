# FIND-018: ChatPanel zeigt generische Fehlermeldung statt strukturierte
Priorität: 🟡 Mittel
Status: Offen
Review: cr-07
CR-AUFG: CR-AUFG-07-25

## Befund

`ChatPanel.tsx:136` ignoriert die vom `useChat`-Hook berechnete actionable
Fehlermeldung und zeigt stattdessen eine generische Konstante:

```tsx
// ChatPanel.tsx:136 (AKTUELL)
{error && <StatusMessage state="error" message={t("chatPanel.errorConnecting")} />}
```

`useChat.ts:88` setzt korrekt `setError(errResponse.userMessage)` (z.B.
"Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen." bei 401),
aber die Komponente verwirft diesen Wert und zeigt `"Verbindungsfehler"`
(`chatPanel.errorConnecting`) — ohne Handlungsempfehlung.

Das widerspricht §16.5 (Error-Message Rule: "[What happened] [What to do]")
für die `chat.free_assistant`-Operation, obwohl der Hook und `mapSSEError`
korrekt arbeiten. Isolierter Befund, kein systematisches Problem — alle anderen
AI-Komponenten nutzen die actionable Message korrekt.

## Evidenz

- `packages/web/.../ChatPanel.tsx:136` — rendert `t("chatPanel.errorConnecting")`
  statt der `error`-Variable.
- `packages/web/lib/hooks/useChat.ts:88` — `setError(errResponse.userMessage)`
  (die korrekte actionable Message).
- `packages/web/lib/api/ai-error-mapping.ts` — `mapSSEError` liefert
  strukturierte `AIErrorResponse` mit i18n-Keys und Handlungsempfehlungen.
- Check 4 (`ai-ux-compliance-v2.md`): verbietet hardcoded `error.message` in
  TSX — ChatPanel umgeht dies durch i18n-Konstante, verliert aber die
  Actionability.

## Auswirkung

Bei Chat-Fehlern (API-Key ungültig, Timeout, Rate-Limit) sieht der Nutzer nur
"Verbindungsfehler" statt der spezifischen Ursache + Handlungsempfehlung
("Überprüfe deinen API-Key"). Der Nutzer weiß nicht, was er tun soll.

## Empfehlung

```tsx
// ChatPanel.tsx (VORGESCHLAGEN)
{error && (
  <StatusMessage
    state="error"
    message={error}  // ← die actionable userMessage aus useChat
    action={aiOp.isError ? { label: t("aiActions.retry"), onClick: aiOp.retry } : undefined}
  />
)}
```

Zusätzlich: `useChat` sollte `error: AIErrorResponse | null` statt `string | null`
zurückgeben, damit `error.retryable` für den Retry-Button verfügbar ist.

**Owner:** Frontend.

## Verifikation

- [ ] `useChat` gibt `error: AIErrorResponse | null` zurück
- [ ] `ChatPanel` rendert `error.userMessage` (nicht generische Konstante)
- [ ] Retry-Button bei `error.retryable === true`
- [ ] Check 4 (`no hardcoded AI error.message in TSX`) bleibt grün
- [ ] Test: 401 → "API-Schlüssel"-Meldung, nicht "Verbindungsfehler"
