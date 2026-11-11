import { type ReactNode } from "react";

// Slow horizontal ticker. The track holds the items twice and slides by half
// its width, so the loop is seamless; the copy is hidden from assistive
// tech. Pauses on hover and stands still under reduced motion.
export default function Marquee({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`mk-marquee overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_6%,black_94%,transparent)] ${className}`}
    >
      <div className="mk-marquee-track flex w-max items-center">
        <div className="flex shrink-0 items-center">{children}</div>
        <div aria-hidden className="flex shrink-0 items-center">
          {children}
        </div>
      </div>
    </div>
  );
}
