// Series artwork (matte black blocks, one lime element). Light pieces are
// rendered on pure white and multiplied into the surface beneath; dark pieces
// are on pure black and lightened into carbon bands. Decorative by default —
// the copy beside it carries the meaning.
export default function Art({
  src,
  width,
  height,
  tone = "light",
  priority = false,
  alt = "",
  className = "",
}: {
  src: string;
  width: number;
  height: number;
  tone?: "light" | "dark";
  // Above-the-fold artwork: load eagerly with high priority.
  priority?: boolean;
  alt?: string;
  className?: string;
}) {
  return (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      fetchPriority={priority ? "high" : "auto"}
      className={`pointer-events-none select-none ${
        tone === "dark" ? "mix-blend-lighten" : "mix-blend-multiply"
      } ${className}`}
    />
  );
}
