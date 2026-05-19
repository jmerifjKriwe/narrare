---
template_type: setting
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  basics:
    label_key: kb.groups.settingBasics
    description_key: kb.groups.settingBasicsHint
    fields:
      genre:
        type: str
        description: Hauptgenre der Geschichte (z.B. Fantasy, Sci-Fi, Historisch)
      time_period:
        type: str
        description: Zeitperiode oder Ära der Geschichte
      tone:
        type: str
        description: Gesamtton (z.B. düster, hoffnungsvoll, satirisch)
      atmosphere:
        type: str
        description: Vorherrschende Atmosphäre oder Stimmung der Welt
  world_rules:
    label_key: kb.groups.settingWorldRules
    description_key: kb.groups.settingWorldRulesHint
    fields:
      magic_level:
        type: str
        description: Grad und Verbreitung von Magie in der Welt
      tech_level:
        type: str
        description: Technologischer Entwicklungsstand
      supernatural_elements:
        type: list
        description: Übernatürliche oder fantastische Elemente
      limitations:
        type: list
        description: Wichtige Einschränkungen dieser Welt
  society:
    label_key: kb.groups.settingSociety
    description_key: kb.groups.settingSocietyHint
    fields:
      political_structure:
        type: str
        description: Regierungssystem (z.B. Monarchie, Demokratie, Theokratie)
      cultural_values:
        type: list
        description: Kulturelle Kernwerte und Überzeugungen
      social_classes:
        type: list
        description: Gesellschaftliche Klassenstruktur
      major_conflicts:
        type: list
        description: Gesellschaftliche Konflikte oder Spannungen
  geography:
    label_key: kb.groups.settingGeography
    description_key: kb.groups.settingGeographyHint
    fields:
      central_location:
        type: str
        description: Zentraler Schauplatz der Geschichte
      landmarks:
        type: list
        description: Wichtige Sehenswürdigkeiten oder Orte
      dangerous_areas:
        type: list
        description: Gefährliche oder verbotene Gebiete
sections:
  world_description:
    label_key: kb.sections.worldDescription
    description_key: kb.sections.worldDescriptionHint
    order: 1
  notes:
    label_key: kb.sections.notes
    description_key: kb.sections.notesHint
    order: 2
---
# Settings-Vorlage

Nutze diese Vorlage, um die weltumspannenden Regeln, Genre-Konventionen
und die atmosphärische Kulisse für deine Geschichte zu definieren.

## Weltbeschreibung

Beschreibe die Welt im Detail — ihre Geografie, den Alltag der Bewohner,
die Machtverhältnisse und was sie einzigartig macht.

## Notizen

Zusätzliche Weltenbau-Notizen, Inspirationen oder Ideen.
