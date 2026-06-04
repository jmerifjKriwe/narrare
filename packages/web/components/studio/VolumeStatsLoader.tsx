"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { volumesApi } from "@/lib/api/client";
import type { UpdateVolumeRequest, Volume } from "@/types";
import { VolumeCard } from "./VolumeCard";

// ---------------------------------------------------------------------------
// Per-volume stats loader
// ---------------------------------------------------------------------------

interface VolumeStatsLoaderProps {
  readonly volume: Volume;
  readonly index: number;
  readonly total: number;
  readonly isEditing: boolean;
  readonly onStartEdit: () => void;
  readonly onCancelEdit: () => void;
  readonly onSave: (id: string, payload: UpdateVolumeRequest) => void;
  readonly onDelete: (id: string) => void;
  readonly onReorderUp: () => void;
  readonly onReorderDown: () => void;
  readonly isSaving: boolean;
}

export function VolumeStatsLoader(props: VolumeStatsLoaderProps) {
  const { volume, index, total, ...cardProps } = props;
  const params = useParams();
  const novelId = params.id as string;

  const { data: stats } = useQuery({
    queryKey: ["novels", novelId, "volumes", volume.id, "stats"],
    queryFn: () => volumesApi.getStats(novelId, volume.id),
    enabled: !!novelId,
  });

  return (
    <VolumeCard
      volume={volume}
      stats={stats}
      isFirst={index === 0}
      isLast={index === total - 1}
      {...cardProps}
    />
  );
}
