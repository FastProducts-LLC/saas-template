import type React from "react";
import {
  useId,
  useState,
  useEffect,
  useLayoutEffect,
  useCallback,
  useRef,
  type SVGProps,
} from "react";
import { createPortal } from "react-dom";

const SPOTLIGHT_GLOW =
  "0 0 0 4px color-mix(in srgb, var(--teal) 30%, transparent), 0 0 20px color-mix(in srgb, var(--teal) 40%, transparent)";

const CARD_WIDTH = 360;
const GAP = 16;
const PADDING = 8;
const EDGE = 20;

const prefersReducedMotion =
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const MOTION = prefersReducedMotion ? "" : "transition-all duration-300 ease-out";

export interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  selector?: string;
  placement: "center" | "top" | "bottom" | "left" | "right";
}

interface OnboardingTourProps {
  isOpen: boolean;
  steps: OnboardingStep[];
  onClose: () => void;
  onComplete: () => void;
}

interface TargetRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

function svgBase(props: SVGProps<SVGSVGElement>): SVGProps<SVGSVGElement> {
  return {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
    ...props,
  };
}

function IconX(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...svgBase(props)}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function IconChevronRight(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...svgBase(props)}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function IconChevronLeft(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...svgBase(props)}>
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

export function OnboardingTour({ isOpen, steps, onClose, onComplete }: OnboardingTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [tooltipHeight, setTooltipHeight] = useState(220);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const titleId = useId();
  const descId = useId();

  const step = steps[currentStep];
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const progress = ((currentStep + 1) / steps.length) * 100;

  useEffect(() => {
    // Resetting internal navigation is intentional when the external dialog opens.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (isOpen) setCurrentStep(0);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !step) return;

    const updateTargetPosition = () => {
      if (step.selector) {
        const element = document.querySelector(step.selector);
        if (element) {
          let rect = element.getBoundingClientRect();
          if (rect.top < 0 || rect.bottom > window.innerHeight) {
            element.scrollIntoView({ block: "center", behavior: "auto" });
            rect = element.getBoundingClientRect();
          }
          setTargetRect({
            top: rect.top - PADDING,
            left: rect.left - PADDING,
            width: rect.width + PADDING * 2,
            height: rect.height + PADDING * 2,
          });

          let top: number;
          let left: number;

          switch (step.placement) {
            case "right":
              top = rect.top + rect.height / 2 - tooltipHeight / 2;
              left = rect.right + GAP;
              if (left + CARD_WIDTH > window.innerWidth - EDGE) left = rect.left - CARD_WIDTH - GAP;
              break;
            case "bottom":
              top = rect.bottom + GAP;
              left = rect.left + rect.width / 2 - CARD_WIDTH / 2;
              if (top + tooltipHeight > window.innerHeight - EDGE)
                top = rect.top - tooltipHeight - GAP;
              break;
            case "top":
              top = rect.top - tooltipHeight - GAP;
              left = rect.left + rect.width / 2 - CARD_WIDTH / 2;
              if (top < EDGE) top = rect.bottom + GAP;
              break;
            case "left":
              top = rect.top + rect.height / 2 - tooltipHeight / 2;
              left = rect.left - CARD_WIDTH - GAP;
              if (left < EDGE) left = rect.right + GAP;
              break;
            default:
              top = window.innerHeight / 2 - tooltipHeight / 2;
              left = window.innerWidth / 2 - CARD_WIDTH / 2;
          }

          top = Math.max(EDGE, Math.min(top, window.innerHeight - tooltipHeight - EDGE));
          left = Math.max(EDGE, Math.min(left, window.innerWidth - CARD_WIDTH - EDGE));

          setTooltipPosition({ top, left });
          return;
        }
      }

      setTargetRect(null);
      setTooltipPosition({
        top: window.innerHeight / 2 - tooltipHeight / 2,
        left: window.innerWidth / 2 - CARD_WIDTH / 2,
      });
    };

    updateTargetPosition();
    window.addEventListener("resize", updateTargetPosition);
    window.addEventListener("scroll", updateTargetPosition, true);
    return () => {
      window.removeEventListener("resize", updateTargetPosition);
      window.removeEventListener("scroll", updateTargetPosition, true);
    };
  }, [isOpen, currentStep, step, tooltipHeight]);

  useLayoutEffect(() => {
    if (!isOpen) return;
    const measured = tooltipRef.current?.offsetHeight;
    if (measured && measured !== tooltipHeight) setTooltipHeight(measured);
  }, [isOpen, currentStep, step, tooltipHeight]);

  const handleNext = useCallback(() => {
    if (isLastStep) {
      onComplete();
      return;
    }
    setCurrentStep((prev) => prev + 1);
  }, [isLastStep, onComplete]);

  const handlePrev = useCallback(() => {
    if (isFirstStep) return;
    setCurrentStep((prev) => prev - 1);
  }, [isFirstStep]);

  const handleSkip = useCallback(() => {
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      const onButton = (e.target as HTMLElement | null)?.tagName === "BUTTON";
      if (e.key === "Escape") handleSkip();
      else if (e.key === "ArrowRight") handleNext();
      else if (e.key === "ArrowLeft") handlePrev();
      else if (e.key === "Enter" && !onButton) handleNext();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleNext, handlePrev, handleSkip]);

  useEffect(() => {
    if (!isOpen) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const id = window.setTimeout(() => {
      tooltipRef.current
        ?.querySelector<HTMLElement>('[data-testid="onboarding-next-button"]')
        ?.focus();
    }, 0);
    return () => {
      window.clearTimeout(id);
      previouslyFocused?.focus?.();
    };
  }, [isOpen]);

  const handleCardKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Tab") return;
    const focusables = tooltipRef.current?.querySelectorAll<HTMLElement>("button");
    if (!focusables || focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);

  if (!isOpen || !step) return null;

  return createPortal(
    <div data-testid="onboarding-tour" className="fixed inset-0 z-[100] pointer-events-none">
      <svg className="absolute inset-0 w-full h-full pointer-events-auto">
        <defs>
          <mask id="onboarding-spotlight-mask">
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            {targetRect && (
              <rect
                x={targetRect.left}
                y={targetRect.top}
                width={targetRect.width}
                height={targetRect.height}
                rx="12"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          fill="rgba(0, 0, 0, 0.75)"
          mask="url(#onboarding-spotlight-mask)"
          onClick={handleSkip}
        />
      </svg>

      {targetRect && (
        <div
          className={`absolute border-2 border-[var(--teal)] rounded-xl pointer-events-none ${MOTION}`}
          style={{
            top: targetRect.top,
            left: targetRect.left,
            width: targetRect.width,
            height: targetRect.height,
            boxShadow: SPOTLIGHT_GLOW,
          }}
        />
      )}

      <div
        ref={tooltipRef}
        data-testid="onboarding-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        onKeyDown={handleCardKeyDown}
        className={`absolute pointer-events-auto ${MOTION}`}
        style={{
          top: tooltipPosition.top,
          left: tooltipPosition.left,
          width: CARD_WIDTH,
        }}
      >
        <div className="rounded-xl border border-[var(--teal)]/30 bg-white/95 shadow-2xl backdrop-blur-sm">
          <div className="flex items-start justify-between gap-3 px-4 pt-4 pb-2">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-[var(--teal)]/10 flex items-center justify-center text-[var(--teal)] shrink-0">
                {step.icon}
              </div>
              <div>
                <h3
                  id={titleId}
                  data-testid="onboarding-title"
                  className="text-base font-semibold leading-tight text-[var(--ink)]"
                >
                  {step.title}
                </h3>
                <p className="text-xs text-[var(--slate)]/70 mt-0.5">
                  Step {currentStep + 1} of {steps.length}
                </p>
              </div>
            </div>
            <button
              type="button"
              data-testid="onboarding-close-button"
              onClick={handleSkip}
              aria-label="Close tour"
              className="h-7 w-7 -mr-1 -mt-1 shrink-0 inline-flex items-center justify-center rounded-md text-[var(--slate)] transition-colors hover:text-[var(--ink)] hover:bg-[var(--paper)]"
            >
              <IconX className="h-4 w-4" />
            </button>
          </div>

          <div className="px-4 pb-3">
            <p
              id={descId}
              data-testid="onboarding-description"
              className="text-sm text-[var(--slate)] leading-relaxed"
            >
              {step.description}
            </p>
          </div>

          <div className="flex flex-col gap-3 px-4 pb-4 pt-0">
            <div className="w-full h-1 bg-[var(--mist)] rounded-full overflow-hidden">
              <div
                className={`h-full bg-[var(--teal)] rounded-full ${MOTION}`}
                style={{ width: `${progress}%` }}
              />
            </div>

            <div className="flex items-center justify-between w-full">
              <button
                type="button"
                data-testid="onboarding-skip-button"
                onClick={handleSkip}
                className="h-8 px-2 inline-flex items-center rounded-md text-sm text-[var(--slate)] transition-colors hover:text-[var(--ink)] hover:bg-[var(--paper)]"
              >
                Skip tour
              </button>

              <div className="flex items-center gap-2">
                {!isFirstStep && (
                  <button
                    type="button"
                    data-testid="onboarding-back-button"
                    onClick={handlePrev}
                    className="h-8 px-3 inline-flex items-center rounded-md border border-[var(--mist)] text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--paper)]"
                  >
                    <IconChevronLeft className="h-4 w-4 mr-1" />
                    Back
                  </button>
                )}
                <button
                  type="button"
                  data-testid="onboarding-next-button"
                  onClick={handleNext}
                  className="h-8 px-3 inline-flex items-center rounded-md bg-[var(--teal)] text-sm font-medium text-white transition-colors hover:bg-[var(--teal-deep)]"
                >
                  {isLastStep ? (
                    "Get Started"
                  ) : (
                    <>
                      Next
                      <IconChevronRight className="h-4 w-4 ml-1" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
