interface NovelDetailsHeaderProps {
  title: string;
  description: string;
}

export function NovelDetailsHeader({ title, description }: NovelDetailsHeaderProps) {
  return (
    <div className="mb-6">
      <h2 className="text-xl font-medium mb-1">{title}</h2>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
