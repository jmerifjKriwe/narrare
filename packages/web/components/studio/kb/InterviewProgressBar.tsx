"use client";

/**
 * InterviewProgressBar — Progress indicator for KB Interview.
 *
 * Extracted from KBInterviewView for RULE-04 file size compliance.
 * Shows a thin progress bar indicating how many fields are filled.
 */

interface InterviewProgressBarProps {
  readonly filledFields: number;
  readonly totalFields: number;
}

export function InterviewProgressBar({ filledFields, totalFields }: InterviewProgressBarProps) {
  return (
    <div className="h-1 bg-muted">
      <div
        className="h-full bg-purple-500 transition-all duration-300"
        style={{ width: totalFields > 0 ? `${(filledFields / totalFields) * 100}%` : "0%" }}
      />
    </div>
  );
}
