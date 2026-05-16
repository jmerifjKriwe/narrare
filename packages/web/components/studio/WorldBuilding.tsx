"use client";

import {
  ChevronRight,
  Church,
  Lightbulb,
  Map as MapIcon,
  MapPin,
  Package,
  Plus,
  Sparkles,
  Trash2,
  User,
  Wand2,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

type EntityType =
  | "characters"
  | "locations"
  | "artifacts"
  | "regions"
  | "religions"
  | "magic"
  | "concepts";

interface Entity {
  id: string;
  type: EntityType;
  name: string;
  subtitle: string;
  description: string;
  notes: string;
}

interface NewEntityForm {
  name: string;
  subtitle: string;
  description: string;
  notes: string;
}

const ENTITY_TYPES: EntityType[] = [
  "characters",
  "locations",
  "artifacts",
  "regions",
  "religions",
  "magic",
  "concepts",
];

const TYPE_ICONS: Record<EntityType, typeof User> = {
  characters: User,
  locations: MapPin,
  artifacts: Package,
  regions: MapIcon,
  religions: Church,
  magic: Wand2,
  concepts: Lightbulb,
};

const MOCK_ENTITIES: Entity[] = [
  {
    id: "1",
    type: "characters",
    name: "Anna Schmidt",
    subtitle: "Protagonistin",
    description:
      "Eine junge Historikerin, die in der Universitätsbibliothek arbeitet. Sie ist intelligent und neugierig, aber auch impulsiv. Nach dem Tod ihres Vaters entdeckt sie Hinweise auf ein Familiengeheimnis.",
    notes: "Charakterentwicklung: Von vorsichtig zu mutig. Beziehung zu Dr. Stein ist komplex.",
  },
  {
    id: "2",
    type: "characters",
    name: "Dr. Viktor Stein",
    subtitle: "Antagonist",
    description:
      "Ein charismatischer Professor für mittelalterliche Geschichte. Äußerlich charmant und hilfsbereit, verfolgt er jedoch eigene dunkle Ziele. Seine Forschungen haben ihn auf die Spur eines alten Geheimnisses gebracht.",
    notes: "Motivation: Macht und Wissen. Geheimnis: Verbindung zum alten Orden.",
  },
  {
    id: "3",
    type: "locations",
    name: "Das Alte Archiv",
    subtitle: "Versteckter Ort",
    description:
      "Ein unterirdisches Archiv beneath der alten Universitätsbibliothek. Jahrhundertealte Dokumente und Artefakte lagern hier in staubigen Regalen. Nur wenige kennen den versteckten Eingang.",
    notes: "Wichtig für: Kapitel 3 und 7. Atmosphäre: Düster, geheimnisvoll.",
  },
  {
    id: "4",
    type: "artifacts",
    name: "Das verschlüsselte Tagebuch",
    subtitle: "Schlüssel-Artefakt",
    description:
      "Ein ledernes Tagebuch aus dem 18. Jahrhundert, das in einer verschlossenen Truhe im Alten Archiv gefunden wurde. Die Seiten enthalten eine komplexe Chiffre, die noch niemand entschlüsseln konnte.",
    notes: "Status: Noch nicht entschlüsselt. Wird in Kapitel 5 gefunden.",
  },
];

const INITIAL_FORM: NewEntityForm = {
  name: "",
  subtitle: "",
  description: "",
  notes: "",
};

interface WorldBuildingProps {
  novelId: string;
}

export function WorldBuilding({ novelId }: WorldBuildingProps) {
  const t = useTranslations("studio");

  // novelId is available for future API calls to fetch novel-specific data
  void novelId;
  const [activeCategory, setActiveCategory] = useState<EntityType>("characters");
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showAIDialog, setShowAIDialog] = useState(false);
  const [newEntity, setNewEntity] = useState<NewEntityForm>(INITIAL_FORM);
  const [aiPrompt, setAiPrompt] = useState("");

  // Derive type config from i18n
  function getTypeConfig(type: EntityType) {
    return {
      label: t(`worldbuilding.${type}.label`),
      singular: t(`worldbuilding.${type}.singular`),
      article: t(`worldbuilding.${type}.article`),
      subtitleLabel: t(`worldbuilding.${type}.subtitleLabel`),
      subtitlePlaceholder: t(`worldbuilding.${type}.subtitlePlaceholder`),
    };
  }

  const config = getTypeConfig(activeCategory);
  const filteredEntities = MOCK_ENTITIES.filter((e) => e.type === activeCategory);
  const selectedEntity = MOCK_ENTITIES.find((e) => e.id === selectedEntityId) ?? null;

  function getCountForType(type: EntityType): number {
    return MOCK_ENTITIES.filter((e) => e.type === type).length;
  }

  function handleStartCreate() {
    setIsCreating(true);
    setSelectedEntityId(null);
    setNewEntity(INITIAL_FORM);
  }

  function handleCancelCreate() {
    setIsCreating(false);
    setNewEntity(INITIAL_FORM);
  }

  function handleCreateEntity() {
    // Mock — would call API
    setIsCreating(false);
    setNewEntity(INITIAL_FORM);
  }

  function handleDeleteEntity() {
    // Mock — would call API
    setSelectedEntityId(null);
  }

  function handleAICreate() {
    // Mock — would call API
    setShowAIDialog(false);
    setAiPrompt("");
  }

  // --- Category Sidebar (Column 1) ---
  const categorySidebar = (
    <div className="w-56 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          {t("worldbuilding.categories")}
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-0.5">
          {ENTITY_TYPES.map((type) => {
            const Icon = TYPE_ICONS[type];
            const isActive = activeCategory === type;
            const count = getCountForType(type);
            const tc = getTypeConfig(type);
            return (
              <button
                type="button"
                key={type}
                onClick={() => {
                  setActiveCategory(type);
                  setSelectedEntityId(null);
                  setIsCreating(false);
                }}
                className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-md transition-all text-sm ${
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "hover:bg-accent text-foreground"
                }`}
              >
                <span className="flex items-center gap-3">
                  <Icon className="w-4 h-4" />
                  <span>{tc.label}</span>
                </span>
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${
                    isActive ? "bg-primary-foreground/20" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );

  // --- Entity List (Column 2) ---
  const entityList = (
    <div className="w-64 border-r border-border bg-muted/30 flex flex-col">
      <div className="p-3 border-b border-border space-y-2">
        <button
          type="button"
          onClick={handleStartCreate}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>{t("worldbuilding.newEntity")}</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setShowAIDialog(true);
            setAiPrompt("");
          }}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-border bg-card rounded-md hover:bg-accent transition-colors text-sm"
        >
          <Sparkles className="w-4 h-4" />
          <span>{t("worldbuilding.aiCreate")}</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {filteredEntities.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground text-sm">
            {(() => {
              const TypeIcon = TYPE_ICONS[activeCategory];
              return <TypeIcon className="w-8 h-8 mx-auto mb-2 opacity-20" />;
            })()}
            <p>{t("worldbuilding.empty", { label: config.label })}</p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {filteredEntities.map((entity) => {
              const Icon = TYPE_ICONS[entity.type];
              const isSelected = selectedEntityId === entity.id;
              return (
                <button
                  type="button"
                  key={entity.id}
                  onClick={() => {
                    setSelectedEntityId(entity.id);
                    setIsCreating(false);
                  }}
                  className={`w-full text-left px-3 py-2.5 rounded-md transition-all ${
                    isSelected ? "bg-card shadow-sm border border-border" : "hover:bg-card/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <div className="min-w-0">
                        <div className="truncate text-sm">{entity.name}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {entity.subtitle}
                        </div>
                      </div>
                    </div>
                    {isSelected && (
                      <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );

  // --- Detail Panel (Column 3) ---
  const ActiveIcon = TYPE_ICONS[activeCategory];

  const detailPanel = (
    <div className="flex-1 overflow-y-auto bg-background">
      <div className="max-w-3xl mx-auto p-8">
        {isCreating ? (
          /* Creating mode */
          <div>
            <div className="flex items-center gap-4 mb-8">
              <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center">
                <Plus className="w-6 h-6 text-muted-foreground" />
              </div>
              <div>
                <h2 className="text-xl font-medium">
                  {t("worldbuilding.createPrompt", {
                    article: config.article,
                    singular: config.singular,
                  })}
                </h2>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="entity-name"
                  className="block text-sm font-medium text-muted-foreground mb-1.5"
                >
                  {t("worldbuilding.name")}
                </label>
                <input
                  id="entity-name"
                  type="text"
                  value={newEntity.name}
                  onChange={(e) => setNewEntity((f) => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
                  placeholder={t("worldbuilding.namePlaceholder", {
                    singular: config.singular,
                  })}
                />
              </div>
              <div>
                <label
                  htmlFor="entity-subtitle"
                  className="block text-sm font-medium text-muted-foreground mb-1.5"
                >
                  {config.subtitleLabel}
                </label>
                <input
                  id="entity-subtitle"
                  type="text"
                  value={newEntity.subtitle}
                  onChange={(e) => setNewEntity((f) => ({ ...f, subtitle: e.target.value }))}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
                  placeholder={config.subtitlePlaceholder}
                />
              </div>
              <div>
                <label
                  htmlFor="entity-description"
                  className="block text-sm font-medium text-muted-foreground mb-1.5"
                >
                  {t("worldbuilding.description")}
                </label>
                <textarea
                  id="entity-description"
                  value={newEntity.description}
                  onChange={(e) => setNewEntity((f) => ({ ...f, description: e.target.value }))}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[100px] resize-y"
                  placeholder={t("worldbuilding.descriptionPlaceholder")}
                />
              </div>
              <div>
                <label
                  htmlFor="entity-notes"
                  className="block text-sm font-medium text-muted-foreground mb-1.5"
                >
                  {t("worldbuilding.notes")}
                </label>
                <textarea
                  id="entity-notes"
                  value={newEntity.notes}
                  onChange={(e) => setNewEntity((f) => ({ ...f, notes: e.target.value }))}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[80px] resize-y"
                  placeholder={t("worldbuilding.notesPlaceholder")}
                />
              </div>
              <div className="flex items-center gap-3 pt-4">
                <button
                  type="button"
                  onClick={handleCreateEntity}
                  className="flex items-center gap-2 px-5 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm text-sm"
                >
                  {t("worldbuilding.createButton")}
                </button>
                <button
                  type="button"
                  onClick={handleCancelCreate}
                  className="flex items-center gap-2 px-5 py-2 border border-border rounded-md hover:bg-accent transition-colors text-sm"
                >
                  {t("worldbuilding.cancelButton")}
                </button>
              </div>
            </div>
          </div>
        ) : selectedEntity ? (
          /* Viewing/editing mode */
          <div>
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center">
                  {(() => {
                    const Icon = TYPE_ICONS[selectedEntity.type];
                    return <Icon className="w-6 h-6 text-muted-foreground" />;
                  })()}
                </div>
                <div>
                  <input
                    type="text"
                    defaultValue={selectedEntity.name}
                    className="text-2xl font-medium bg-transparent border-none outline-none w-full"
                  />
                  <input
                    type="text"
                    defaultValue={selectedEntity.subtitle}
                    className="text-sm text-muted-foreground bg-transparent border-none outline-none w-full mt-1"
                  />
                </div>
              </div>
              <button
                type="button"
                onClick={handleDeleteEntity}
                className="p-2 text-destructive hover:bg-destructive/10 rounded-md"
                aria-label={t("worldbuilding.deleteButton")}
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-6">
              <div>
                <label
                  htmlFor="detail-description"
                  className="block text-sm font-medium text-muted-foreground mb-1.5"
                >
                  {t("worldbuilding.description")}
                </label>
                <textarea
                  id="detail-description"
                  defaultValue={selectedEntity.description}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[120px] resize-y"
                />
              </div>
              <div>
                <label
                  htmlFor="detail-notes"
                  className="block text-sm font-medium text-muted-foreground mb-1.5"
                >
                  {t("worldbuilding.notes")}
                </label>
                <textarea
                  id="detail-notes"
                  defaultValue={selectedEntity.notes}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[100px] resize-y"
                />
              </div>
            </div>
          </div>
        ) : (
          /* Empty state */
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-muted-foreground">
            <ActiveIcon className="w-16 h-16 mx-auto mb-4 opacity-10" />
            <p className="text-lg mb-1">
              {t("worldbuilding.selectEntity", {
                article: config.article,
                singular: config.singular,
              })}
            </p>
            <p className="text-sm">{t("worldbuilding.orCreate", { article: config.article })}</p>
          </div>
        )}
      </div>
    </div>
  );

  // --- AI Create Dialog ---
  const aiDialog = showAIDialog && (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl max-w-xl w-full overflow-hidden">
        <div className="p-6 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <h3 className="font-medium">
              {t("worldbuilding.aiDialog.title", {
                singular: config.singular,
              })}
            </h3>
          </div>
          <button
            type="button"
            onClick={() => setShowAIDialog(false)}
            className="p-1 hover:bg-accent rounded-md"
            aria-label={t("worldbuilding.cancelButton")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6">
          <label htmlFor="ai-prompt" className="block text-sm font-medium mb-2">
            {t("worldbuilding.aiDialog.promptLabel")}
          </label>
          <textarea
            id="ai-prompt"
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[120px] resize-y"
            placeholder={t("worldbuilding.aiDialog.promptPlaceholder")}
          />
          <p className="text-xs text-muted-foreground mt-2">
            {t("worldbuilding.aiDialog.hint", {
              article: config.article,
              singular: config.singular,
            })}
          </p>
        </div>
        <div className="p-6 border-t border-border flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => setShowAIDialog(false)}
            className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-accent transition-colors text-sm"
          >
            {t("worldbuilding.cancelButton")}
          </button>
          <button
            type="button"
            onClick={handleAICreate}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm"
          >
            <Sparkles className="w-4 h-4" />
            {t("worldbuilding.aiDialog.createButton")}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <div className="flex-1 flex h-full">
        {categorySidebar}
        {entityList}
        {detailPanel}
      </div>
      {aiDialog}
    </>
  );
}
