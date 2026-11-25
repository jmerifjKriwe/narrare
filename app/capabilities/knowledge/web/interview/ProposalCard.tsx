/**
 * The interview's proposal (W9 Task 10): the draft the interview has built so
 * far — name, type, aliases, tags, description and the proposed relations —
 * with the server's provenance drawn honestly. Every part the model proposed
 * carries «vorgeschlagen» exactly as the wire marks it (per item for a list,
 * per slot for the scalars); an open field says «noch offen»; and while any
 * mark stands, «Vorschläge verwerfen» offers the one act that clears them all.
 * The card collapses but never hides its readiness: the header is a button.
 */
import { useId } from "react";

import type { Proposal } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { CARD_EYEBROW, FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { relationTypeLabel } from "../relations";
import { SuggestedMark } from "../SuggestedMark";

function hasSuggestedPart(proposal: Proposal): boolean {
  return (
    proposal.name_suggested ||
    (proposal.suggested?.aliases?.length ?? 0) > 0 ||
    (proposal.suggested?.tags?.length ?? 0) > 0 ||
    proposal.suggested?.content === true ||
    (proposal.relations ?? []).some((relation) => relation.suggested)
  );
}

export function ProposalCard({
  proposal,
  typeLabel,
  expanded,
  onToggle,
  onDropSuggestions,
  dropping,
}: {
  proposal: Proposal | null;
  typeLabel: string;
  expanded: boolean;
  onToggle: () => void;
  onDropSuggestions: () => void;
  dropping: boolean;
}) {
  const t = useTranslation();
  const bodyId = useId();
  const name = proposal?.name?.trim() ?? "";
  const aliases = proposal?.aliases ?? [];
  const tags = proposal?.tags ?? [];
  const content = proposal?.content?.trim() ?? "";
  const relations = proposal?.relations ?? [];
  const suggestedAliases = proposal?.suggested?.aliases ?? [];
  const suggestedTags = proposal?.suggested?.tags ?? [];
  const anySuggested = proposal !== null && hasSuggestedPart(proposal);

  return (
    <section
      data-testid="entity-interview-proposal"
      aria-label={t("knowledge.interview.proposalTitle")}
      className="mx-3 mt-3 shrink-0 overflow-hidden rounded-[var(--radius-surface)] border border-rule bg-card shadow-card"
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={onToggle}
        className={`flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-surface-container-low ${FOCUS}`}
      >
        <span className={CARD_EYEBROW}>{t("knowledge.interview.proposalTitle")}</span>
        <span className="flex items-center gap-2">
          <span className="text-[10px] text-primary">{typeLabel}</span>
          <span className="text-muted">
            <Icon name={expanded ? "expandLess" : "chevronDown"} size={16} />
          </span>
        </span>
      </button>
      {expanded && (
        <div id={bodyId} className="px-3 pb-3">
          <dl className="flex flex-col gap-2 text-meta">
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted">{t("knowledge.interview.nameLabel")}</dt>
              <dd className="flex items-center gap-1.5">
                {name !== "" ? (
                  <span className="font-semibold text-foreground">{name}</span>
                ) : (
                  <span className="italic text-muted">{t("knowledge.interview.openValue")}</span>
                )}
                {proposal?.name_suggested && <SuggestedMark />}
              </dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted">{t("knowledge.interview.typeLabel")}</dt>
              <dd className="text-foreground">{typeLabel}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted">{t("knowledge.interview.aliasesLabel")}</dt>
              <dd className="flex flex-wrap gap-1">
                {aliases.length === 0 ? (
                  <span className="italic text-muted">{t("knowledge.interview.openValue")}</span>
                ) : (
                  aliases.map((alias) => (
                    <span key={alias} className="inline-flex items-center gap-1 rounded bg-surface-container-low px-1.5 py-0.5 text-[10px] text-foreground">
                      {alias}
                      {suggestedAliases.includes(alias) && <SuggestedMark />}
                    </span>
                  ))
                )}
              </dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted">{t("knowledge.interview.tagsLabel")}</dt>
              <dd className="flex flex-wrap gap-1">
                {tags.length === 0 ? (
                  <span className="italic text-muted">{t("knowledge.interview.openValue")}</span>
                ) : (
                  tags.map((tag) => (
                    <span key={tag} className="inline-flex items-center gap-1 rounded bg-surface-container-low px-1.5 py-0.5 text-[10px] text-foreground">
                      {tag}
                      {suggestedTags.includes(tag) && <SuggestedMark />}
                    </span>
                  ))
                )}
              </dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className="flex items-center gap-1 text-muted">
                {t("knowledge.interview.descriptionLabel")}
                {proposal?.suggested?.content === true && <SuggestedMark />}
              </dt>
              {content !== "" ? (
                <dd className="whitespace-pre-line leading-snug text-foreground">{content}</dd>
              ) : (
                <dd className="italic text-muted">{t("knowledge.interview.openValue")}</dd>
              )}
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted">{t("knowledge.interview.relationsLabel")}</dt>
              <dd className="flex flex-col gap-1">
                {relations.length === 0 ? (
                  <span className="italic text-muted">{t("knowledge.interview.openValue")}</span>
                ) : (
                  relations.map((relation, index) => (
                    <span
                      key={`${relation.target}\u0000${relation.type}\u0000${index}`}
                      className="flex items-start justify-between gap-1 rounded border border-rule bg-surface-container-low/60 px-2 py-1 text-[11px] text-foreground"
                    >
                      <span>
                        {relation.target} — {relationTypeLabel(t, relation.type)}
                        {relation.note !== "" && <span className="block text-muted">{relation.note}</span>}
                      </span>
                      {relation.suggested && <SuggestedMark />}
                    </span>
                  ))
                )}
              </dd>
            </div>
          </dl>
          {anySuggested && (
            <div className="mt-2 border-t border-rule pt-1 text-right">
              <button
                type="button"
                data-testid="entity-interview-drop-suggestions"
                disabled={dropping}
                onClick={onDropSuggestions}
                className={`text-[10px] text-muted underline decoration-rule transition-colors hover:text-danger disabled:cursor-not-allowed ${FOCUS}`}
              >
                {t("knowledge.interview.dropSuggestions")}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
