interface HeroStatProps {
  label: string;
  value: string;
}

export function HeroStat({ label, value }: HeroStatProps) {
  return (
    <div className="hero-stat">
      <div className="value num">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}
