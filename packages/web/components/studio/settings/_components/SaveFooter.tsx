"use client";

interface SaveFooterProps {
  dirty: boolean;
  isSaving: boolean;
  isError: boolean;
  onSave: () => void;
  errorText: string;
  saveText: string;
  loadingText: string;
}

export function SaveFooter({
  dirty,
  isSaving,
  isError,
  onSave,
  errorText,
  saveText,
  loadingText,
}: SaveFooterProps) {
  return (
    <>
      {/* Error message */}
      {isError && <div className="text-sm text-destructive">{errorText}</div>}

      {/* Save button */}
      {dirty && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onSave}
            disabled={isSaving}
            className="px-6 py-2.5 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm text-sm disabled:opacity-50"
          >
            {isSaving ? loadingText : saveText}
          </button>
        </div>
      )}
    </>
  );
}
