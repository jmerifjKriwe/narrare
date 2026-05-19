---
template_type: concept
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  definition:
    label_key: kb.groups.conceptDefinition
    description_key: kb.groups.conceptDefinitionHint
    fields:
      category:
        type: str
        description: Kategorie des Konzepts (z.B. Technologie, Gesellschaft, Magie, Philosophie)
      summary:
        type: str
        description: Kurze Zusammenfassung des Konzepts in einem Satz
      key_principles:
        type: list
        description: Kernprinzipien oder Grundsätze dieses Konzepts
      rules:
        type: list
        description: Spezifische Regeln oder Gesetze dieses Konzepts
      implications:
        type: str
        description: Auswirkungen des Konzepts auf die Welt
  history:
    label_key: kb.groups.conceptHistory
    description_key: kb.groups.conceptHistoryHint
    fields:
      origin:
        type: str
        description: Ursprung des Konzepts
      discovery:
        type: str
        description: Wie das Konzept entdeckt oder bekannt wurde
      key_figures:
        type: list
        description: Wichtige Persönlichkeiten dieses Konzepts
      evolution:
        type: str
        description: Wie sich das Konzept im Laufe der Zeit entwickelt hat
sections:
  description:
    label_key: kb.sections.description
    description_key: kb.sections.descriptionHint
    order: 1
  implications:
    label_key: kb.sections.implications
    description_key: kb.sections.implicationsHint
    order: 2
---
# Konzept-Vorlage

Nutze diese Vorlage, um abstrakte Weltenbau-Elemente wie Technologien,
Magiesysteme, philosophische Ideen oder soziale Strukturen zu definieren.

## Beschreibung

Beschreibe das Konzept ausführlich — wie es funktioniert, wer damit interagiert
und welche Rolle es in der Welt spielt.

## Auswirkungen

Beschreibe die weiteren Auswirkungen des Konzepts — wie beeinflusst es
Gesellschaft, Technologie, Kultur oder den Konflikt der Geschichte?
