interface AuthErrorProps {
  message: string;
}

export function AuthError({ message }: AuthErrorProps) {
  return (
    <div
      data-testid="auth-error"
      className="bg-destructive/10 text-destructive rounded-md p-3 text-sm border-l-2 border-l-destructive"
    >
      {message}
    </div>
  );
}
