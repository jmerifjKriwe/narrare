/**
 * FieldGroupSection — Grouping wrapper for field list sections.
 *
 * Extracted from KBSessionFieldList for RULE-04 compliance.
 */

interface FieldGroupSectionProps {
  title: string;
  count: number;
  titleClassName: string;
  children: React.ReactNode;
}

export function FieldGroupSection({
  title,
  count,
  titleClassName,
  children,
}: FieldGroupSectionProps) {
  return (
    <div>
      <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 ${titleClassName}`}>
        {title} ({count})
      </h4>
      <div className="space-y-2">{children}</div>
    </div>
  );
}
