interface ROIDisplayProps {
  roi: number;
}

export function ROIDisplay({ roi }: ROIDisplayProps) {
  const aboveTarget = roi >= 9.8;
  return (
    <div
      className={`rounded-full border px-4 py-3 text-right shadow-soft ${
        aboveTarget ? "border-moss/25 bg-moss/10" : "border-sunrise/30 bg-sunrise/10"
      }`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/60">ROI</p>
      <p className="font-display text-2xl text-ink">{roi.toFixed(1)} words/hr</p>
      <p className="text-xs text-ink/55">Target benchmark: 9.8</p>
    </div>
  );
}
