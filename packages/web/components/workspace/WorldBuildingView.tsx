"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import {
  type LucideIcon,
  User,
  MapPin,
  Package,
  MapIcon,
  Church,
  Wand2,
  Lightbulb,
  Plus,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { NameGeneratorModal } from "@/components/generation/NameGeneratorModal";

// ---------------------------------------------------------------------------
// Entity category configuration
// ---------------------------------------------------------------------------

type EntityType =
  | "characters"
  | "locations"
  | "artifacts"
  | "regions"
  | "religions"
  | "magic"
  | "concepts";

interface EntityCategoryConfig {
  icon: LucideIcon;
  labelKey: string;
  singularKey: string;
}

const ENTITY_CONFIG: Record<EntityType, EntityCategoryConfig> = {
  characters: { icon: User, labelKey: "wb_characters", singularKey: "wb_character" },
  locations: { icon: MapPin, labelKey: "wb_locations", singularKey: "wb_location" },
  artifacts: { icon: Package, labelKey: "wb_artifacts", singularKey: "wb_artifact" },
  regions: { icon: MapIcon, labelKey: "wb_regions", singularKey: "wb_region" },
  religions: { icon: Church, labelKey: "wb_religions", singularKey: "wb_religion" },
  magic: { icon: Wand2, labelKey: "wb_magic", singularKey: "wb_magicSystem" },
  concepts: { icon: Lightbulb, labelKey: "wb_concepts", singularKey: "wb_concept" },
};

const CATEGORY_ORDER: EntityType[] = [
  "characters",
  "locations",
  "artifacts",
  "regions",
  "religions",
  "magic",
  "concepts",
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface WorldBuildingViewProps {
  novelId: string;
}

// ---------------------------------------------------------------------------
// WorldBuildingView — 3-column layout stub
// ---------------------------------------------------------------------------

export function WorldBuildingView({ novelId }: WorldBuildingViewProps) {
  const t = useTranslations("editor");
  const [activeCategory, setActiveCategory] = useState<EntityType>("characters");
  const [showNameGenerator, setShowNameGenerator] = useState(false);

  const config = ENTITY_CONFIG[activeCategory];
  const CategoryIcon = config.icon;

  return (
    <div className="flex-1 flex h-full">
      {/* Category Sidebar */}
      <div className="w-56 border-r border-border bg-card flex flex-col shrink-0">
        <div className="p-4 border-b border-border">
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            {t("wb_categories")}
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <div className="space-y-0.5">
            {CATEGORY_ORDER.map((type) => {
              const TypeIcon = ENTITY_CONFIG[type].icon;
              const isActive = activeCategory === type;
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => setActiveCategory(type)}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 rounded-md transition-all text-sm cursor-pointer border-none",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "hover:bg-accent text-foreground bg-transparent",
                  )}
                >
                  <TypeIcon className="w-4 h-4" />
                  <span>{t(ENTITY_CONFIG[type].labelKey)}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Entity List */}
      <div className="w-64 border-r border-border bg-muted/30 flex flex-col shrink-0">
        <div className="p-3 border-b border-border space-y-2">
          <button
            type="button"
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm cursor-pointer border-none"
            onClick={() => {
              // Stub — placeholder dialog
              alert(t("wb_comingSoon"));
            }}
          >
            <Plus className="w-4 h-4" />
            {t("wb_createNew")}
          </button>
          <button
            type="button"
            className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-border bg-card rounded-md hover:bg-accent transition-colors text-sm cursor-pointer"
            onClick={() => setShowNameGenerator(true)}
          >
            <Sparkles className="w-4 h-4" />
            {t("wb_createWithAI")}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {/* Empty state */}
          <div className="text-center py-12 text-muted-foreground text-sm">
            <CategoryIcon className="w-8 h-8 mx-auto mb-2 opacity-20" />
            <p>{t("wb_noEntities", { type: t(config.labelKey) })}</p>
            <p className="text-xs mt-1">
              {t("wb_createFirst", { type: t(config.singularKey) })}
            </p>
          </div>
        </div>
      </div>

      {/* Detail Panel */}
      <div className="flex-1 overflow-y-auto bg-background">
        <div className="flex items-center justify-center h-full text-muted-foreground">
          <div className="text-center">
            <CategoryIcon className="w-16 h-16 mx-auto mb-4 opacity-10" />
            <p className="text-lg mb-1">
              {t("wb_selectEntity", { type: t(config.singularKey) })}
            </p>
            <p className="text-sm">{t("wb_orCreate")}</p>
          </div>
        </div>
      </div>

      {/* Name Generator Modal — "Create with AI" */}
      <NameGeneratorModal
        projectId={novelId}
        isOpen={showNameGenerator}
        onClose={() => setShowNameGenerator(false)}
      />
    </div>
  );
}
