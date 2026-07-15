/**
 * useInterviewHistory — accumulates interview Q&A pairs for post-completion
 * review.
 *
 * The interview flow (KBInterviewView) is linear: each answer is submitted
 * and the textarea is reset. Without an accumulator the Q&A is lost.
 * This hook owns that list so the view component stays presentation-light
 * (RULE-06) and KBInterviewView stays within the RULE-04 line budget.
 */

import { useCallback, useState } from "react";

/** A single recorded question/answer exchange from the interview. */
export interface InterviewQAEntry {
  /** The AI-generated question text. */
  readonly question: string;
  /** The user's answer, as typed. */
  readonly answer: string;
  /** The target field the question was about (may be empty for free-form Q). */
  readonly fieldKey: string;
}

export function useInterviewHistory() {
  const [entries, setEntries] = useState<InterviewQAEntry[]>([]);

  /** Append a Q&A pair. Called once per submitted answer. */
  const addEntry = useCallback((entry: InterviewQAEntry) => {
    setEntries((prev) => [...prev, entry]);
  }, []);

  return { entries, addEntry };
}
