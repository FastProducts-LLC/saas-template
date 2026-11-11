// Inline SVG sparkline — the records-instrument trend signal.
// Monochrome ink line + teal fill, hairline stroke, tabular-nums labels.
// No external chart library: keeps the bundle lean and the visual language
// consistent with DESIGN.md (hairline rules, one signal color).

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string; // stroke color
  fill?: string; // area fill
  "data-testid"?: string;
}

export default function Sparkline({
  data,
  width = 120,
  height = 36,
  color = "var(--teal-deep)",
  fill = "var(--teal)",
  "data-testid": testId,
}: SparklineProps) {
  if (data.length < 2) {
    return (
      <svg
        data-testid={testId}
        width={width}
        height={height}
        className="inline-block"
        aria-label="Not enough data for trend"
      />
    );
  }

  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const pad = 2;

  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = height - pad - ((v - min) / range) * (height - pad * 2);
    return [x, y] as const;
  });

  const linePath = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");

  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;

  return (
    <svg
      data-testid={testId}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="inline-block overflow-visible"
      aria-label={`Trend over ${data.length} points`}
    >
      <path d={areaPath} fill={fill} opacity={0.1} />
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle
        cx={points[points.length - 1][0]}
        cy={points[points.length - 1][1]}
        r={2.5}
        fill={color}
      />
    </svg>
  );
}
