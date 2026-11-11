// Scroll reveal for marketing sections: fades the block up the first time it
// enters the viewport (styles: .mk-reveal in index.css). Content is shown
// immediately where IntersectionObserver is unavailable, and reduced-motion
// users never see the hidden state.

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

export default function Reveal({
  children,
  className = "",
  index = 0,
  "data-testid": testId,
}: {
  children: ReactNode;
  className?: string;
  // Stagger position among siblings revealed together.
  index?: number;
  "data-testid"?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(() => typeof IntersectionObserver === "undefined");

  useEffect(() => {
    const el = ref.current;
    if (!el || shown) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [shown]);

  return (
    <div
      ref={ref}
      data-testid={testId}
      className={`mk-reveal ${shown ? "is-in" : ""} ${className}`}
      style={{ "--i": index } as CSSProperties}
    >
      {children}
    </div>
  );
}
