import { useCallback, useEffect, useRef, useState } from "react";

import { useRouter } from "@tanstack/react-router";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { LeaveBlocker } from "@shell/components/LeaveBlocker";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Notice } from "@shell/ui/Notice";

import { ModelsSection } from "./ModelsSection";
import { ProvidersSection, type Guard, type Provider } from "./ProvidersSection";
import { TasksSection } from "./TasksSection";

type Model = components["schemas"]["ModelRead"];
type Assignment = components["schemas"]["AssignmentRead"];
type TaskEffective = components["schemas"]["TaskEffectiveRead"];

/**
 * The provider surface, composed of its three sections: the providers (the
 * endpoints their models hang off), the models (which provider serves which
 * model string, and how it is tuned), and the tasks (which model serves
 * which task key). The panel owns what the sections share — the mount's
 * four reads, the load failure with its retry, and the one leave guard for
 * both forms — so a section stays a form and a list, and the page keeps one
 * dialog, one ask, and one place that says "the load failed".
 */
export function ProvidersPanel() {
  const t = useTranslation();
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [models, setModels] = useState<Model[] | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [tasks, setTasks] = useState<TaskEffective[]>([]);
  const [failure, setFailure] = useState<MessageKey | null>(null);

  useEffect(() => {
    // All four views load on mount: the task selects and their effective
    // lines display out of these lists, so a fresh visit must show the
    // stored choices — not "automatic" until some later mutation happens to
    // refetch them. A navigation away during that first fetch must not
    // write into an unmounted panel; the flag is the smallest guard, and
    // React's no-op setState is not a contract to rely on.
    let cancelled = false;
    void reload(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, []);

  async function reload(cancelled: () => boolean = () => false): Promise<void> {
    // The four reads fail independently: a lost key that fails /tasks must
    // not also hide the providers and models that did arrive. Settled
    // results keep every success, and the panel's alert names the failure.
    const [providerList, modelList, assignmentList, taskList] = await Promise.allSettled([
      client.GET("/api/settings/providers"),
      client.GET("/api/settings/profiles"),
      client.GET("/api/settings/assignments"),
      client.GET("/api/settings/tasks"),
    ]);
    if (cancelled()) return;
    let failed = false;
    if (providerList.status === "fulfilled" && providerList.value.response.ok) {
      setProviders(providerList.value.data ?? []);
    } else {
      failed = true;
    }
    if (modelList.status === "fulfilled" && modelList.value.response.ok) {
      setModels(modelList.value.data ?? []);
    } else {
      failed = true;
    }
    if (assignmentList.status === "fulfilled" && assignmentList.value.response.ok) {
      setAssignments(assignmentList.value.data ?? []);
    } else {
      failed = true;
    }
    if (taskList.status === "fulfilled" && taskList.value.response.ok) {
      setTasks(taskList.value.data ?? []);
    } else {
      failed = true;
    }
    setFailure(failed ? "settings.profiles.errorLoad" : null);
  }

  // The two form sections report their dirtiness here: one leave guard for
  // the page, whoever is holding typed values.
  const dirtyParts = useRef({ providers: false, models: false });
  const [dirty, setDirty] = useState(false);
  const markDirty = useCallback((part: "providers" | "models", value: boolean) => {
    dirtyParts.current[part] = value;
    setDirty(dirtyParts.current.providers || dirtyParts.current.models);
  }, []);

  const [guardOpen, setGuardOpen] = useState(false);
  const guardAnswer = useRef<((leave: boolean) => void) | null>(null);

  /** Resolve the standing ask; a dismissed dialog means "stay". */
  function settle(leave: boolean): void {
    const answer = guardAnswer.current;
    guardAnswer.current = null;
    setGuardOpen(false);
    answer?.(leave);
  }

  /** Ask before typed values are discarded; a second ask while one stands is a no. */
  function askToLeave(): Promise<boolean> {
    if (guardAnswer.current !== null) return Promise.resolve(false);
    setGuardOpen(true);
    return new Promise<boolean>((resolve) => {
      guardAnswer.current = resolve;
    });
  }

  const guard: Guard = { dirty, ask: askToLeave };
  const onProviderDirty = useCallback((value: boolean) => markDirty("providers", value), [markDirty]);
  const onModelDirty = useCallback((value: boolean) => markDirty("models", value), [markDirty]);

  // The third door: a route change with a dirty form asks too. The blocker
  // mounts only where a router exists, so the panel stays renderable alone.
  const router = useRouter({ warn: false });

  return (
    <>
      <ProvidersSection
        providers={providers}
        reload={reload}
        guard={guard}
        onDirty={onProviderDirty}
      />
      <ModelsSection
        providers={providers}
        models={models}
        reload={reload}
        guard={guard}
        onDirty={onModelDirty}
      />
      <TasksSection
        models={models}
        assignments={assignments}
        tasks={tasks}
        reload={reload}
      />

      {failure !== null ? (
        // The reads failed: said where the way back is — one press asks
        // all four again, no reload demanded.
        <Notice
          tone="danger"
          live="alert"
          className="mt-3"
          action={
            <Button variant="secondary" onClick={() => void reload()}>
              {t("settings.retry")}
            </Button>
          }
        >
          {t(failure)}
        </Notice>
      ) : null}

      {router ? <LeaveBlocker dirty={dirty} ask={askToLeave} /> : null}

      <Dialog
        title={t("save.leaveTitle")}
        isOpen={guardOpen}
        onOpenChange={(open) => {
          if (!open) settle(false);
        }}
      >
        {(close) => (
          <>
            <p className="mt-2 text-body text-muted">{t("dirty.confirmLeave")}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  settle(false);
                  close();
                }}
              >
                {t("save.leaveStay")}
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  settle(true);
                  close();
                }}
              >
                {t("save.leaveGo")}
              </Button>
            </div>
          </>
        )}
      </Dialog>
    </>
  );
}
