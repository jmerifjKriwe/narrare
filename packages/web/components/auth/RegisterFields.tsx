interface RegisterFieldsProps {
  displayName: string;
  email: string;
  password: string;
  onDisplayNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  t: (key: string) => string;
}

export function RegisterFields({
  displayName,
  email,
  password,
  onDisplayNameChange,
  onEmailChange,
  onPasswordChange,
  t,
}: RegisterFieldsProps) {
  return (
    <>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="register-display-name" className="text-sm font-medium text-foreground">
          {t("displayName")}
        </label>
        <input
          id="register-display-name"
          type="text"
          value={displayName}
          onChange={(e) => onDisplayNameChange(e.target.value)}
          placeholder={t("displayNamePlaceholder")}
          autoComplete="name"
          className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="register-email" className="text-sm font-medium text-foreground">
          {t("email")}
        </label>
        <input
          id="register-email"
          type="email"
          required
          value={email}
          onChange={(e) => onEmailChange(e.target.value)}
          placeholder={t("emailPlaceholder")}
          autoComplete="email"
          // biome-ignore lint/a11y/noAutofocus: intentional focus on register email field
          autoFocus
          className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="register-password" className="text-sm font-medium text-foreground">
          {t("password")}
        </label>
        <input
          id="register-password"
          type="password"
          required
          value={password}
          onChange={(e) => onPasswordChange(e.target.value)}
          placeholder={t("passwordPlaceholder")}
          autoComplete="new-password"
          className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
        />
      </div>
    </>
  );
}
