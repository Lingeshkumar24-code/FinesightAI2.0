interface BadgeProps {
  level: string; // e.g. "low" | "moderate" | "high" | "critical" | "on_track" | "watch" | "breach"
  children: React.ReactNode;
}

export function Badge({ level, children }: BadgeProps) {
  return <span className={`badge ${level}`}>{children}</span>;
}
