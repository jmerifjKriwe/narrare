"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { volumesApi } from "@/lib/api/client";
import type { CreateVolumeRequest, UpdateVolumeRequest } from "@/types";
import { VolumeFormFields } from "./VolumeCard";
import { VolumeStatsLoader } from "./VolumeStatsLoader";

// ---------------------------------------------------------------------------
// Main View
// ---------------------------------------------------------------------------

export function VolumeManagementView() {
  const t = useTranslations("studio");
  const params = useParams();
  const novelId = params.id as string;
  const queryClient = useQueryClient();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // Create form state
  const [createTitle, setCreateTitle] = useState("");
  const [createSubtitle, setCreateSubtitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createTarget, setCreateTarget] = useState("");

  // Fetch volumes
  const { data: volumes = [], isLoading } = useQuery({
    queryKey: ["novels", novelId, "volumes"],
    queryFn: () => volumesApi.list(novelId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateVolumeRequest) => volumesApi.create(novelId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels", novelId, "volumes"] });
      setShowCreate(false);
      resetCreateForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateVolumeRequest }) =>
      volumesApi.update(novelId, id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels", novelId, "volumes"] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => volumesApi.delete(novelId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels", novelId, "volumes"] });
    },
  });

  const reorderMutation = useMutation({
    mutationFn: (volumeIds: string[]) => volumesApi.reorder(novelId, volumeIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels", novelId, "volumes"] });
    },
  });

  function resetCreateForm() {
    setCreateTitle("");
    setCreateSubtitle("");
    setCreateDescription("");
    setCreateTarget("");
  }

  function handleReorderUp(index: number) {
    if (index <= 0) return;
    const ids = volumes.map((v) => v.id);
    [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
    reorderMutation.mutate(ids);
  }

  function handleReorderDown(index: number) {
    if (index >= volumes.length - 1) return;
    const ids = volumes.map((v) => v.id);
    [ids[index], ids[index + 1]] = [ids[index + 1], ids[index]];
    reorderMutation.mutate(ids);
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-medium">{t("volumes.title")}</h1>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm text-sm"
          >
            <Plus className="w-4 h-4" />
            <span>{t("volumes.createVolume")}</span>
          </button>
        </div>

        {/* Create form */}
        {showCreate && (
          <VolumeFormFields
            title={createTitle}
            subtitle={createSubtitle}
            description={createDescription}
            target={createTarget}
            onTitleChange={setCreateTitle}
            onSubtitleChange={setCreateSubtitle}
            onDescriptionChange={setCreateDescription}
            onTargetChange={setCreateTarget}
            onSubmit={() => {
              createMutation.mutate({
                title: createTitle,
                subtitle: createSubtitle || null,
                description: createDescription || null,
                word_count_target: createTarget ? Number(createTarget) : null,
              });
            }}
            onCancel={() => {
              setShowCreate(false);
              resetCreateForm();
            }}
            submitLabel={t("volumes.createVolume")}
            isPending={createMutation.isPending}
          />
        )}

        {/* Volume list */}
        <div className="space-y-3">
          {volumes.map((volume, index) => (
            <VolumeStatsLoader
              key={volume.id}
              volume={volume}
              index={index}
              total={volumes.length}
              isEditing={editingId === volume.id}
              onStartEdit={() => setEditingId(volume.id)}
              onCancelEdit={() => setEditingId(null)}
              onSave={(id, payload) => updateMutation.mutate({ id, payload })}
              onDelete={(id) => deleteMutation.mutate(id)}
              onReorderUp={() => handleReorderUp(index)}
              onReorderDown={() => handleReorderDown(index)}
              isSaving={updateMutation.isPending}
            />
          ))}
        </div>

        {/* Empty state */}
        {volumes.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-8">{t("volumes.noTarget")}</p>
        )}
      </div>
    </div>
  );
}
