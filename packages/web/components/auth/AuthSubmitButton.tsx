interface AuthSubmitButtonProps {
  isSubmitting: boolean;
  loadingLabel: string;
  submitLabel: string;
}

export function AuthSubmitButton({
  isSubmitting,
  loadingLabel,
  submitLabel,
}: AuthSubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={isSubmitting}
      className="mt-2 h-9 w-full rounded-md bg-primary text-primary-foreground text-sm font-medium shadow-sm hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none transition-colors"
    >
      {isSubmitting ? loadingLabel : submitLabel}
    </button>
  );
}
