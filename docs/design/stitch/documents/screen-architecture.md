# Narrare — Funktionale & Konzeptionelle Screen-Architektur (Backend & KI-Blueprint)
**Plattform:** Narrare — Literarisches Autoren- & Story-Architecture-Atelier  
**Designsystem:** Literary Modernism (V2.4)  
**Zweck dieses Dokuments:** Umfassende funktionale Beschreibung aller Screens, Informationsarchitekturen, Datenmodelle, Interaktionslogiken und KI-Prompting-Verhaltensweisen für Entwickler und Frontend/Backend-KI-Agenten.

---

## 1. Übergeordnete Architektur & Systemphilosophie

Narrare ist kein einfacher Texteditor, sondern eine **literarische Realitäts- und Kausalitäts-Engine**. Die Benutzeroberfläche spiegelt die Denkweise professioneller Romanautoren wider:
1. **Der Text ist nur die Oberfläche eines Eisbergs:** Unter jedem Absatz liegt ein Netz aus Figuren, Schauplätzen, historischen Zeitlinien, Kausalitätsketten und wissenschaftlichen/recherchebasierten Belegen.
2. **Kausalität vor Textgenerierung:** Bevor eine KI Text vorschlägt oder ein Autor weiterschreibt, prüft das System, ob das Geschriebene im Einklang mit dem bisherigen Kanon steht. Widersprüche werden sofort visualisiert.
3. **Typografische Kontemplation:** Die UI nutzt das haptische Gefühl von Büttenpapier (`#fff8f2`), Buchdrucker-Terracotta (`#743b1f`) und edler Typografie (`Newsreader` für Prosa, `Plus Jakarta Sans` für UI, `Courier Prime` für Normseiten).

---

## 2. Modul- & Screen-Spezifikationen im Detail

### MODULGRUPPE A: Atelier-Einstieg, Setup & Orientierung

#### 1. Bücherregal & Bibliotheksverwaltung (`{{DATA:SCREEN:SCREEN_81}}`)
* **Gedanke & Mental Model:** Der Autor betritt sein physisches Schreibzimmer. Jedes Projekt erscheint wie ein gebundenes Buch im Regal. Es geht um Wertschätzung des eigenen Schaffens.
* **Informationsarchitektur & Daten:**
  - Aktives Projekt (Hero-Card mit großem Buchcover, Fortschrittsbalken, aktuellem Wortstand z. B. `48.342 / 65.000 W.`, letzter Bearbeitungszeitpunkt).
  - Sekundäre Projekte (Grid mit Cover-Miniaturen, Genre-Pill, Wortzähler, Schnellauswahlmenü: Duplizieren, Exportieren, Archivieren).
  - Primäraktion: `+ Neues Buch anlegen` oder `Manuskript importieren`.
* **Interaktionslogik:** Klick auf ein Buch lädt den Zustand und wechselt direkt in die letzte aktive Szene des Schreib-Workspace. Hover-Zustand zeigt Buchrücken-Tiefeneffekt.

#### 2. Willkommen & Autoren-Onboarding (`{{DATA:SCREEN:SCREEN_51}}`)
* **Gedanke & Mental Model:** Minimalistisches, zentriertes Ritual (ohne störende Navigationsleisten). Der Autor wird nicht mit Formularen bombardiert, sondern wählt seine literarische Arbeitsweise.
* **Dargestellte Informationen & Schritte:**
  - Moduswahl: *Der Architekt (Plotter / Outliner)* vs. *Der Entdecker (Pantser / Discovery Writer)* vs. *Der Hybrid (Plantser)*.
  - Zieldefinition: Genre, geplanter Umfang (z. B. 65.000 Wörter NaNoWriMo oder 120.000 Wörter High Fantasy), Abgabetermin.
  - Tonalitäts-Initialisierung: Wie soll der KI-Partner agieren? (z. B. „Strenger Lektor“, „Sokratischer Fragesteller“, „Atmosphärischer Co-Autor“).
* **KI-Logik:** Legt die globalen Prompt-Systemregeln für das Projekt fest.

#### 3. Manuskript- & Lore-Import Studio (`{{DATA:SCREEN:SCREEN_53}}`)
* **Gedanke & Mental Model:** Bestehende Manuskripte (aus Word, Scrivener, Papyrus oder Markdown) sollen nicht als „dummer Textklumpen“ importiert werden, sondern automatisch in Entitäten, Szenen und Zeitlinien zerlegt werden.
* **Dargestellte Informationen:**
  - Drag-and-Drop-Zone für `.docx`, `.scriv`, `.epub`, `.md`.
  - KI-Analyse-Vorschau: Automatisch erkannte Kapitel, extrahierte Figuren (z. B. „Dr. Maya Chen“, „Director Kavic“), Schauplätze und Zeitepochen.
  - Mapping-Konfigurator: Zuordnung erkannter Überschriften zu Akten und Szenen.
* **KI-Logik:** Hintergrund-Parsing mit Named Entity Recognition (NER) und Zeitstrahl-Extraktion.

#### 4. Atelier-Einstellungen & KI-Regelwerk (`{{DATA:SCREEN:SCREEN_55}}`)
* **Gedanke & Mental Model:** Absolute Transparenz und Kontrolle über das Verhalten der KI. Autoren fürchten Kontrollverlust; hier wird festgelegt, was die KI darf und was tabu ist.
* **Dargestellte Informationen:**
  - *Autonomie-Schieberegler:* Von „Reine Faktenprüfung & Rechtschreibung“ bis „Aktive Textweiterführung“.
  - *Kanon-Strenge:* Wie hart soll die Kausalitäts-Engine sein? (Tolerant bei Metaphern vs. Nulltoleranz bei Zeitachsenbrüchen).
  - *API- & Provider-Wahl:* Auswahl des KI-Modells, API-Keys, Token-Budget-Deckelung.
  - *Shortcuts-Übersicht:* Alle Tastaturkommandos für unterbrechungsfreies Schreiben.

#### 5. Befehlspalette & Universalsuche (⌘K) (`{{DATA:SCREEN:SCREEN_23}}`)
* **Gedanke & Mental Model:** Die Schaltzentrale für Tastatur-Power-User. Der Autor muss nie die Hände von der Tastatur nehmen.
* **Dargestellte Informationen:**
  - Fuzzy-Search über Manuskripttext, Figurendossiers, Glossareinträge, Recherche-Notizen und Szenen.
  - Quick Actions: `Gehe zu Akt 2, Szene 4`, `Figur Maya Chen öffnen`, `Konsistenzprüfung starten`, `In Zen-Modus wechseln`.
  - Tastatur-Hints (z. B. `Tab` zum Autocomplete, `Esc` zum Schließen).

---

### MODULGRUPPE B: Schreib-Erlebnis & Workflow

#### 6. Integrierte Gesamtsuite (`{{DATA:SCREEN:SCREEN_73}}`)
* **Gedanke:** Die Meisteransicht für große Bildschirme. Sie verbindet Navigation, Kapitelstruktur, Schreib-Canvas und das Knowledge-Dock zu einem synchronen Dreiklang.
* **Struktur:**
  - Linke Spalte (240px): Projekt-Navigation & Szenenbaum.
  - Mitte (Hauptteil): Satzspiegel-Manuskript (optimal 680–740px Lesebreite) mit Zählern.
  - Rechte Spalte (360px): Kontextsensitives Dock (wechselt automatisch zwischen Lore-Karten, Notizen und Recherche passend zum Cursor-Ort im Text).

#### 7. Schreib-Workspace (`{{DATA:SCREEN:SCREEN_79}}`, `{{DATA:SCREEN:SCREEN_75}}`, `{{DATA:SCREEN:SCREEN_43}}`)
* **Gedanke:** Das Herzstück des Autors. Das Layout priorisiert typografische Ruhe und Lesbarkeit.
* **Dargestellte Informationen:**
  - *Sub-Header:* Buch- und Kapitelpfad (`Dead Signal / Kapitel 2: Nevada Echoes`), Live-Wortzähler (z. B. `48.342 / 65.000 W.`), Kausalitäts-Badge (`Kausalität synchron`).
  - *Editorfläche:* Warmes Naturpapier, Schrift `Newsreader`, 18px, Zeilenabstand 1.75. 
  - *Inline-Ghost-Text:* Dezent kursiv gesetzte Textweiterführungsvorschläge der KI, die mit `Tab` übernommen oder durch Weitertippen verworfen werden können.
  - *Floating Toolbar:* Formatierung, Szenen-Trenner (`§§§`), KI-Aktionen (`Subtext analysieren`, `Zeige Zeitleiste an dieser Stelle`).

#### 8. Zen-Fokus & Atmosphärischer Schreibmodus (`{{DATA:SCREEN:SCREEN_7}}`)
* **Gedanke & Mental Model:** Vollständige digitale Klausur. Alle Werkzeuge, Menüs, Sidebars und Benachrichtigungen verschwinden.
* **Dargestellte Informationen:**
  - Nur der reine Text in der Mitte des Bildschirms.
  - *Typewriter Scrolling & Focus:* Der aktive Absatz hat 100% Kontrast; vorangehende und folgende Absätze dimmen auf 35% Deckkraft ab, um den Blick im Fluss zu halten.
  - *Atmosphärische Fußleiste (schwebend):* Ambient-Sound-Mixer (z. B. 45% Permafrost-Wind + Konsolenbrummen für die Eisstations-Atmosphäre), Sprint-Timer und Wortzähler für die aktuelle Session (+642 Wörter heute).
  - Rückkehr mit `Esc` in die Studioansicht.

#### 9. Revisions- & Diff-Historie (Time-Machine) (`{{DATA:SCREEN:SCREEN_49}}`)
* **Gedanke:** Keine Angst vor dem Löschen. Ein literarisches Versionskontrollsystem (Git für Autoren), das Änderungen semantisch begreift.
* **Dargestellte Informationen:**
  - Zeitachsen-Slider mit gespeicherten Meilensteinen (z. B. „Vor Kausalitäts-Korrektur“, „Lektorat Alpha-Fassung“).
  - Zweispaltiger Diff-Vergleich: Gelöschte Textpassagen in warmem Muted-Rot durchgestrichen, neue Sätze in Kausal-Grün hervorgehoben.
  - Rollback-Option: Punktuelles Zurückholen einzelner Absätze, ohne das gesamte Dokument zu überschreiben.

#### 10. Audio- & Diktat-Studio (Voice-to-Lore) (`{{DATA:SCREEN:SCREEN_19}}`)
* **Gedanke:** Autoren plotten oft beim Spazierengehen. Das System erfasst spontane Sprachmemos, transkribiert sie und trennt Story-Ideen automatisch von Szenentext.
* **Dargestellte Informationen:**
  - Audiowellenform-Visualisierer mit Aufnahmesteuerung.
  - Live-Transkription in Echtzeit.
  - KI-Klassifikator: Markiert im Text automatisch: „Das ist ein Dialogschnipsel für Maya“, „Das ist ein neuer Lore-Fakt über die Station“, „Das ist eine ToDo-Notiz für Kapitel 5“.

#### 11. Narrare Pocket (Mobile Web / App) (`{{DATA:SCREEN:SCREEN_11}}`)
* **Gedanke:** Das Atelier für die Hosentasche. Schnelles Festhalten von Ideen im Bus oder Café, synchron mit dem Desktop.
* **Dargestellte Informationen:**
  - Optimiertes 390px-Raster mit unterer Tab-Navigation: *Ideen*, *Manuskript*, *Lore*, *Audio*.
  - Große One-Tap-Sprachaufnahmetaste.
  - Kartenansicht für schnelle Entitäten-Checks (Wer war Dr. Chen nochmal?).

---

### MODULGRUPPE C: Kausalität, Weltenbau & Dramaturgie

#### 12. Kausalitäts-Matrix & Plot-Twist-Simulator (What-If Engine) (`{{DATA:SCREEN:SCREEN_5}}`)
* **Gedanke:** Autoren scheuen Plot-Twists im späten Manuskript, weil sie fürchten, die Konsistenz früherer/späterer Kapitel zu zerstören. Dieser Screen simuliert die Auswirkungen von Änderungen wie ein Kausalitäts-Debugger.
* **Dargestellte Informationen & Struktur:**
  - *Linke Spalte (Branch-Navigator):* Auswahl zwischen `Kanon Alpha` und alternativen Zweigen (z. B. `Branch Beta: Maya öffnet Schleuse nicht`). Schieberegler für Figuren-Loyalität und Statuswerte.
  - *Mitte (Verzweigungsgraph & Ripple-Tracker):* Zeigt den Bruchpunkt. Grün = unveränderte Kapitel; Gelb = Schauplatz-/Textverschiebung; Rot = **Kollision / Paradoxon**.
  - *Rechte Spalte (Kausalitäts-Inspektor):* Listet präzise Fehler auf (z. B. „Wenn Schleuse zu bleibt, kann Dr. Chen in Kapitel 14 nicht auf der Relais-Station sein, da kein Sauerstoff mehr da war“).
  - *Aktionen:* `Zusatz-Szene 8b einschieben`, `Branch mergen`, `Als alternatives Spin-off exportieren`.

#### 13. Großansichten des Entitäten- & Lore-Graphen (`{{DATA:SCREEN:SCREEN_71}}`, `{{DATA:SCREEN:SCREEN_63}}`, `{{DATA:SCREEN:SCREEN_57}}`)
* **Gedanke:** Die visuelle Repräsentation des Weltenbau-Wissensnetzwerks.
* **Dargestellte Informationen:**
  - Interaktiver 2D-Node-Graph mit Physik-Simulation.
  - *Knoten-Typen:* Figuren (Kreise mit Monogramm/Porträt), Schauplätze (Quadrate mit Standort-Icon), Artefakte/Technologie (Rauten), Ereignisse (Punkte auf Zeitachsen).
  - *Kanten-Semantik:* Beschriftete Vektoren (z. B. `schwester von`, `stationiert auf`, `weiß über Verrat`).
  - *Kollisions-Visualisierung:* Rote pulsierende Verbindungen zeigen logische Brüche (z. B. Station 7 vs. Station 9).
  - Detail-Drawer am unteren/rechten Rand bei Klick auf einen Knoten mit Attributen und Fundstellen im Text.

#### 14. 3-Akt-Storyboard & Szenen-Struktur (`{{DATA:SCREEN:SCREEN_67}}`)
* **Gedanke:** Klassische dramaturgische Struktur (Exposition, Plot Point 1, Konfrontation, Midpoint, Climax, Resolution) visuell handhabbar machen.
* **Dargestellte Informationen:**
  - Horizontale Akt-Spalten (Akt I, Akt II-A, Akt II-B, Akt III) mit dramaturgischem Spannungsbogen (Beats).
  - Szenenkarten mit: Titel, POV-Figur, Handlungsort, Wortzahl-Status, Ziel der Szene und Konflikt-Zusammenfassung.
  - Drag-and-Drop zur Neuordnung der Kapitelreihenfolge (mit automatischer Kausalitätswarnung bei Brüchen).

#### 15. Chronologie- & Timeline-Ansicht (`{{DATA:SCREEN:SCREEN_69}}`)
* **Gedanke:** Unterscheidung zwischen *Fabula* (reale zeitliche Abfolge) und *Sujet* (Reihenfolge der Erzählung im Roman / Rückblenden).
* **Dargestellte Informationen:**
  - Absolute Zeitachse (z. B. Jahre 2083 bis 2094).
  - Parallel-Spuren für verschiedene Handlungsstränge und Figuren (Maya auf Station 7, Director Kavic auf der Erde).
  - Markierung von Flashbacks und Zeitsprüngen.

#### 16. Weltenbau- & Geografie-Atlas (Light & Dark Mode) (`{{DATA:SCREEN:SCREEN_35}}`, `{{DATA:SCREEN:SCREEN_25}}`)
* **Gedanke:** Das geografische und geopolitische Fundament fiktiver Welten.
* **Dargestellte Informationen:**
  - Karten-Canvas mit Ebenen-Steuerung (Topografie, politische Grenzen, Versorgungsrouten, Stations-Grundrisse).
  - Orts-Dossiers mit Klimadaten, Jurisdiktion, Reisedauern zwischen Schauplätzen und Liste aller dort spielenden Szenen.
  - Dark Mode: Perfekt für Sci-Fi-Sternenkarten oder nächtliche Schreibphasen.

#### 17. Serien- & Mehrbänder-Architektur (Light & Dark Mode) (`{{DATA:SCREEN:SCREEN_33}}`, `{{DATA:SCREEN:SCREEN_27}}`)
* **Gedanke:** Steuerung mehrteiliger Romanzyklen (Trilogien, Epen). Verhindert, dass Figuren in Band III Fähigkeiten besitzen, die in Band I ausgeschlossen wurden.
* **Dargestellte Informationen:**
  - Multi-Book-Timeline: Bogen über Band 1 (*Dead Signal*), Band 2 und Band 3.
  - Figuren-Entwicklungs-Matrizen (Wie wandelt sich Mayas psychologischer Zustand über die Bücher?).
  - Unaufgelöste Mysterien & Foreshadowing-Register.

---

### MODULGRUPPE D: Figuren, Dialoge & Recherche

#### 18. Figuren- & Schauplatz-Dossiers (`{{DATA:SCREEN:SCREEN_47}}`, `{{DATA:SCREEN:SCREEN_45}}`)
* **Gedanke:** Tiefenpsychologische Profile statt flacher Steckbriefe.
* **Dargestellte Informationen:**
  - Basisdaten: Name, Rolle, Alter, Zugehörigkeit, optische Merkmale.
  - Psychologischer Kern: Äußerer Wunsch (*Want*) vs. Inneres Bedürfnis (*Need*), die fundamentale Lebenslüge (*The Lie*), Traumata und Trigger.
  - Beziehungs-Netzwerk mit dynamischem Loyalitäts-Score zu anderen Charakteren.
  - Zitat- und Dialog-Auszüge direkt aus dem Manuskript verlinkt.

#### 19. Dialog-Stimm-Labor & Figuren-Simulator (`{{DATA:SCREEN:SCREEN_15}}`)
* **Gedanke:** Verhindert das Problem, dass alle Figuren gleich klingen (der sogenannte „Autor-Monolog“). Das Modul fungiert als interaktiver Sparring-Partner.
* **Dargestellte Informationen & Struktur:**
  - *Idiolekt-Regler:* Wortschatz-Dichte, Satzlänge, Emotionalität, Sarkasmus-Grad, Fachjargon-Anteil.
  - *Live-Chat-Simulator:* Der Autor spricht eine Figur an („Maya, warum hast du Kavic angelogen?“), und die KI antwortet streng im psychologischen und sprachlichen Profil der Figur.
  - *Stimmen-Audit:* Analyse eines bestehenden Dialogs auf Konsistenz der Figurenstimmen.

#### 20. Entitäten-Genesis im KI-Dialog (`{{DATA:SCREEN:SCREEN_39}}`)
* **Gedanke:** Organisches Erschaffen neuer Charaktere, Artefakte oder Schauplätze im Dialog, statt statische Formulare auszufüllen.
* **Dargestellte Informationen:**
  - Sokratischer Chatverlauf: Die KI hinterfragt Motivationen („Wenn sie Physikerin ist, warum war sie 2083 in Nevada?“).
  - Live-generierte Steckbrief-Karte auf der rechten Seite, die sich mit jedem Dialogschritt mit Attributen und Lore-Belegen füllt.
  - Button: `In Kanon aufnehmen & im Lore-Graph verankern`.

#### 21. Quellen-, Recherche- & Fakten-Archiv (`{{DATA:SCREEN:SCREEN_13}}`)
* **Gedanke:** Für Hard-Sci-Fi, historische Romane oder Thriller. Jede Behauptung im Text wird mit realen oder fiktiven Quellen belegt.
* **Dargestellte Informationen:**
  - Quellensammlung (PDFs, Web-Links, USGS-Messdaten, historische Auszüge).
  - Verknüpfung von Textstellen mit Fußnoten/Belegen.
  - Faktencheck-Score: Wie viele Aussagen im Kapitel sind belegt vs. reine Autorenhypothese?

---

### MODULGRUPPE E: Lektorat, Analyse & Produktivität

#### 22. Subtext- & Szenen-Sezierer (`{{DATA:SCREEN:SCREEN_31}}`)
* **Gedanke:** Ein professioneller Lektor bewertet nicht Grammatik, sondern das, was *zwischen den Zeilen* steht.
* **Dargestellte Informationen:**
  - Dreistufiges Zeilenscanning: *Text* (gesprochenes Wort), *Subtext* (was die Figur wirklich denkt), *Dramaturgische Spannung* (Wer hat die Macht in dieser Sekunde?).
  - Spannungs-Kurve über die Szene: Wo bricht das Pacing ein? Wo plätschert der Dialog?

#### 23. Lektorats- & Kommentar-Workspace (`{{DATA:SCREEN:SCREEN_21}}`)
* **Gedanke:** Zusammenarbeit mit menschlichen Testlesern, Lektoren oder dem KI-Lektor.
* **Dargestellte Informationen:**
  - Marginalien-Spalte mit farbcodierten Anmerkungen (Gelb = Stil/Formulierung, Rot = Plot-Loch, Grün = Lob/Starke Passage).
  - Kommentar-Threads mit Antwortfunktion und `Als gelöst markieren`.

#### 24. Beta-Reader & Literarische Analyse-Suite (`{{DATA:SCREEN:SCREEN_41}}`)
* **Gedanke:** Simuliert eine heterogene Testleserschaft, bevor das Buch an einen Verlag geht.
* **Dargestellte Informationen:**
  - Verschiedene Testleser-Personas (z. B. „Der Gelegenheitsleser“, „Der Hard-Sci-Fi-Purist“, „Der Romance-Fokussierte“).
  - Feedback-Matrizen zu: Sympathie der Protagonistin, Nachvollziehbarkeit des Twists, Langeweile-Zonen (Choke Points).
  - Sentiment-Verlaufskurve über alle Kapitel.

#### 25. Autoren-Produktivität & Schreib-Analytik (`{{DATA:SCREEN:SCREEN_17}}`)
* **Gedanke:** Schreibblockaden lösen durch datengestützte Gewohnheiten ohne toxischen Druck.
* **Dargestellte Informationen:**
  - Wortzahl-Burndown-Chart gegen die Verlags-Deadline.
  - Tageszeit-Analyse: Wann schreibt der Autor mit der höchsten Taktung und den wenigsten Löschungen?
  - Streak-Kalender und VG-Wort-Normseiten-Zähler.

---

### MODULGRUPPE F: Buchgestaltung, Vermarktung & Verlags-Pipeline

#### 26. Cover-, Klappentext- & Marketing-Studio (`{{DATA:SCREEN:SCREEN_9}}`)
* **Gedanke:** Das Manuskript ist fertig – jetzt wird es zu einem verkaufsfähigen Produkt.
* **Dargestellte Informationen & Struktur:**
  - *Zentrum (3D-Buchmockup):* Fotorealistisches Hardcover mit Schutzumschlag und Gold-/Kupferheißfolienprägung. Ansichten für Isometrie, Frontal, Druckbogen, Kindle und Hörbuch-Cover.
  - *Links (Produktions-Parameter):* Exakter Rückenbreiten-Kalkulator (z. B. 26,4 mm bei 420 S. 80g Werkdruck), ISBN- & EAN-13-Vektorgenerator mit Preisaufdruck.
  - *Rechts (Klappentext & Social Kits):* KI-Textoptimierer für Buchrückentext (148 Wörter), Social-Media-Karussells und Amazon A+-Banner.

#### 27. Export- & Buchsatz-Studio (Print & ePub) (`{{DATA:SCREEN:SCREEN_37}}`)
* **Gedanke:** Ersetzt teure Buchsatzprogramme wie Adobe InDesign oder Vellum. Druckfertige PDFs und valide ePub3-Dateien auf Knopfdruck.
* **Dargestellte Informationen:**
  - Satzspiegel-Vorschau mit Buchblock-Doppelseite, Stegen, Kolumnentiteln und Paginierung.
  - Typografische Feineinstellungen: Schusterjungen- und Hurenkinder-Vermeidung, Ligaturen, Initialen (Drop Caps) und Schnittmarken.
  - Export-Profile: KDP (Amazon), IngramSpark, Tolino, Lokale Druckerei (CMYK/FOGRA51).

#### 28. Exposé- & Pitch-Studio (`{{DATA:SCREEN:SCREEN_29}}`)
* **Gedanke:** Die Erstellung des gefürchteten Verlags-Exposés.
* **Dargestellte Informationen:**
  - Strukturierte Vorlage: 1-Satz-Logline, Pitch-Absatz, Zielgruppen- & Marktanalyse, vollständige Synopsis inklusive Ende.
  - Vergleichstitel (*Comp Titles*): „Trifft Stanislaw Lem auf Arrival“.

#### 29. Agentur-, Verlags- & Einreichungs-Manager (`{{DATA:SCREEN:SCREEN_3}}`)
* **Gedanke:** Strukturierte Verfolgung der Verlagssuche statt unübersichtlicher Excel-Tabellen.
* **Dargestellte Informationen:**
  - KPI-Dashboard: Rechercheierte Agenturen (18), aktive Pitches (5), Full Requests (2), Angebote (1).
  - Kanban-Pipeline: *Recherche* → *Gepitcht* → *Full Request* → *Angebot/Vertrag*.
  - Normseiten-Vorschau nach offiziellem VG-Wort-Standard (30 Zeilen à 60 Anschläge).
  - Lizenz- und Rechtematrix (Hardcover, Taschenbuch, Hörbuch, Übersetzung).

---

## 3. Dialog-Design & Interaktionsmuster für KI-Assistenten

Damit eine KI in Narrare natürlich, nützlich und nicht bevormundend agiert, gelten feste Interaktionsmuster:

### A. Der "Ghost-Prompting"-Dialog (Im Manuskript)
* **Trigger:** Der Autor pausiert für 1.5 Sekunden am Satzende.
* **Darstellung:** Sehr dezent grauer/kursiver Text (`#b5a598`), der sich organisch an den Cursor anfügt.
* **Interaktion:**
  - `Tab`: Vollständige Übernahme.
  - `Shift + Tab`: Alternative Formulierung generieren.
  - Weiteres normales Tippen: Vorschlag verschwindet spurlos ohne Rückfrage.

### B. Der Kausalitäts-Kollisions-Dialog (Lore-Alert)
* **Trigger:** Der Autor tippt einen Satz, der einem etablierten Fakt widerspricht (z. B. Maya behauptet, ihre Schwester sei in New York gestorben, im Dossier steht Nevada).
* **Darstellung:**
  - Eine feine bernsteinfarbene Unterwellung unter dem Satz.
  - Ein dezentes Badge am rechten Rand (`Paradoxon entdeckt`).
  - Bei Klick öffnet sich ein nicht-blockierender Popover mit zwei Optionen:
    1. *„Im Text anpassen“* (ersetzt New York mit Nevada).
    2. *„Lore aktualisieren“* (übernimmt New York als neuen Kanon und passt alle Dossiers an).

### C. Der Dialog-Simulator (Figuren-Sparring)
* **Darstellung:** Split-Screen-Chatfenster mit Monogramm-Avatar der Figur.
* **Verhalten:** Die KI spricht strikt in der ersten Person als die Figur. Sie hat nur Zugriff auf Informationen, die die Figur zu diesem Zeitpunkt der Handlung wissen kann (kein allwissender KI-Blickwinkel).

---

## 4. Datenmodell & Schema-Blueprint (Zusammenfassung)

```json
{
  "project": {
    "id": "book_dead_signal_01",
    "title": "Dead Signal",
    "genre": "Hard Science Fiction Noir",
    "meta": { "target_words": 65000, "current_words": 48342 },
    "canon": {
      "entities": [
        {
          "id": "ent_maya_chen",
          "type": "CHARACTER",
          "name": "Dr. Maya Chen",
          "psychology": { "want": "Die Wahrheit über das Signal", "need": "Abschied nehmen" },
          "relations": [{ "target": "ent_station_7", "type": "stationed_at" }]
        },
        {
          "id": "ent_station_7",
          "type": "LOCATION",
          "name": "Forschungsstation 7 (Nevada Deep-Array)",
          "status": "HAVARIERT"
        }
      ],
      "events": [
        { "id": "ev_01", "timestamp": "2083-11-04", "title": "Schleusen-Vorfall", "impact_entities": ["ent_station_7"] }
      ]
    }
  }
}
```

Mit dieser Spezifikation ist jeder Bildschirm, jedes Modul und jede Interaktion lückenlos für Entwickler und KI-Systeme definiert.
