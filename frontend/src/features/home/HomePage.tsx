// Public landing page layout; product story lives in shared/content/marketing.ts.
// Built from the marketing design system (DESIGN.md, shared/ui/marketing):
// white canvas, carbon type, one lime accent, sand bento panels, block artwork.

import { useState, type CSSProperties } from "react";

import { useAuth } from "../auth";
import { EVENTS } from "../../shared/lib/events";
import { track } from "../../shared/lib/track";
import { ROUTES } from "../../shared/lib/routes";
import { HOME_CONTENT, type Faq } from "../../shared/content/marketing";
import {
  Art,
  Chip,
  Eyebrow,
  Ledger,
  Marquee,
  MK_BODY,
  MK_DISPLAY,
  MK_H2,
  MK_H3,
  MK_H4,
  MK_INDEX,
  MK_LEAD,
  MK_MONO,
  MK_STATEMENT,
  MK_WRAP,
  MkButton,
  Panel,
  Reveal,
} from "../../shared/ui/marketing";
import closingArt from "../../shared/assets/art/closing.webp";
import engineArt from "../../shared/assets/art/engine.webp";
import explodedArt from "../../shared/assets/art/exploded.webp";
import faqArt from "../../shared/assets/art/faq.webp";
import adminArt from "../../shared/assets/art/feature-admin.webp";
import creditsArt from "../../shared/assets/art/feature-credits.webp";
import keysArt from "../../shared/assets/art/feature-keys.webp";
import meteredArt from "../../shared/assets/art/feature-metered.webp";
import orgsArt from "../../shared/assets/art/feature-orgs.webp";
import privacyArt from "../../shared/assets/art/feature-privacy.webp";
import heroArt from "../../shared/assets/art/hero.webp";
import cloneArt from "../../shared/assets/art/step-clone.webp";
import meterArt from "../../shared/assets/art/step-meter.webp";
import shipArt from "../../shared/assets/art/step-ship.webp";
import sliceArt from "../../shared/assets/art/step-slice.webp";
import MarketingFooter from "./components/MarketingFooter";
import MarketingHeader from "./components/MarketingHeader";

// Decorative artwork, index-aligned with HOME_CONTENT.features / .steps.
const FEATURE_ART = [orgsArt, creditsArt, meteredArt, keysArt, adminArt, privacyArt] as const;
const STEP_ART = [cloneArt, sliceArt, meterArt, shipArt] as const;

// Bento spans on the 6-column desktop grid: two wide cards, three thirds,
// then a full-width closer.
const FEATURE_SPANS = [
  "lg:col-span-3",
  "lg:col-span-3",
  "lg:col-span-2",
  "lg:col-span-2",
  "lg:col-span-2",
  "lg:col-span-6",
] as const;

// Desktop positions of the four mini ledgers around the hero artwork.
const HERO_CARD_SLOTS = [
  "lg:left-12 lg:top-12",
  "lg:right-12 lg:top-9",
  "lg:bottom-12 lg:left-12",
  "lg:bottom-9 lg:right-12",
] as const;

// The ticker needs enough chips to overflow any viewport before it repeats.
const TICKER_REPEAT = 3;

function HeroPanel() {
  const { cards } = HOME_CONTENT.heroPanel;
  return (
    <Panel
      data-testid="home-hero-panel"
      radius="2xl"
      className="gd-hero-in relative overflow-hidden [animation-delay:150ms]"
    >
      <div aria-hidden className="mk-dots absolute inset-0 opacity-70" />
      <div
        aria-hidden
        className="relative mx-auto grid max-w-md gap-3 p-6 sm:grid-cols-2 lg:block lg:h-[520px] lg:max-w-[900px] lg:p-0"
      >
        <div className="mk-glow absolute left-1/2 top-[45%] h-[300px] w-[300px] -translate-x-1/2 -translate-y-1/2 max-lg:top-[110px] lg:h-[460px] lg:w-[460px]" />
        <Art
          src={heroArt}
          width={1536}
          height={864}
          priority
          className="relative h-auto w-full object-contain sm:col-span-2 lg:absolute lg:inset-0 lg:h-full"
        />
        {cards.map((card, i) => (
          <Ledger
            key={card.label}
            label={card.label}
            facts={card.facts}
            live={i % 2 === 0}
            style={{ "--i": i } as CSSProperties}
            className={`mk-float relative lg:absolute lg:z-10 lg:w-[240px] ${HERO_CARD_SLOTS[i]}`}
          />
        ))}
      </div>
    </Panel>
  );
}

function FaqItem({ q, a }: Faq) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-[var(--mk-hair)]">
      <button
        type="button"
        data-testid="home-faq-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-6 py-5 text-left"
      >
        <span className="text-lg text-[var(--carbon)]">{q}</span>
        <span
          aria-hidden
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-lg leading-none transition-all duration-200 ${
            open
              ? "rotate-45 bg-[var(--lime)] text-[var(--carbon)]"
              : "bg-[var(--mk-chip)] text-[var(--mk-muted)]"
          }`}
        >
          +
        </span>
      </button>
      {open && <p className={`${MK_BODY} max-w-2xl pb-6`}>{a}</p>}
    </div>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const primaryHref = user ? ROUTES.dashboard : ROUTES.auth.register;
  const { hero, stack, statement, features, engine, steps, faqs, closing } = HOME_CONTENT;
  const ticker = Array.from({ length: TICKER_REPEAT }, () => stack.items).flat();

  return (
    <div className="mk min-h-screen bg-[var(--canvas)]" data-testid="home-page">
      <MarketingHeader />

      {/* Hero */}
      <section className="relative overflow-hidden pt-16">
        <div
          aria-hidden
          className="mk-dots absolute inset-0 [mask-image:linear-gradient(to_bottom,black,transparent_75%)]"
        />
        <div className={`${MK_WRAP} gd-hero-in relative pb-12 pt-16 sm:pt-20`}>
          <Eyebrow chip={String(features.length).padStart(2, "0")}>{hero.eyebrow}</Eyebrow>
          <h1 className={`mt-5 ${MK_DISPLAY}`}>{hero.headline}</h1>
          <p className={`mt-5 max-w-4xl ${MK_LEAD}`}>{hero.description}</p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <MkButton
              to={primaryHref}
              size="lg"
              onClick={() => track(EVENTS.cta_clicked, { cta: "primary", location: "hero" })}
              data-testid="home-cta-link"
            >
              {user ? hero.signedInLabel : hero.signedOutLabel}
            </MkButton>
            <MkButton
              to={ROUTES.docs}
              variant="soft"
              size="lg"
              onClick={() => track(EVENTS.cta_clicked, { cta: "api_docs", location: "hero" })}
              data-testid="home-docs-link"
            >
              {hero.docsLabel}
              <span aria-hidden>→</span>
            </MkButton>
          </div>
        </div>
        <div className={`${MK_WRAP} relative`}>
          <HeroPanel />
        </div>
      </section>

      {/* Stack ticker */}
      <section className="mt-12 border-y border-[var(--mk-hair)]">
        <div className={`${MK_WRAP} flex items-center gap-6 py-4`}>
          <Eyebrow tone="strong" className="shrink-0">
            {stack.label}:
          </Eyebrow>
          <Marquee className="min-w-0 flex-1">
            {ticker.map((item, i) => (
              <Chip key={`${item}-${i}`} className="mx-1.5">
                {item}
              </Chip>
            ))}
          </Marquee>
        </div>
      </section>

      {/* Statement + exploded view */}
      <section className={`${MK_WRAP} py-20 sm:py-24`}>
        <Reveal className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-16">
          <p className={`max-w-4xl ${MK_STATEMENT}`}>
            {statement.lead} <span className="text-[var(--mk-muted)]">{statement.rest}</span>
          </p>
          <Art
            src={explodedArt}
            width={1024}
            height={1024}
            className="mk-float mx-auto h-auto w-full max-w-[320px] lg:max-w-none"
          />
        </Reveal>
      </section>

      {/* Features — sand bento cards: copy, artwork, mini ledger */}
      <section id="features" className="scroll-mt-20 pb-20 sm:pb-28">
        <div className={MK_WRAP}>
          <Reveal>
            <Eyebrow>{HOME_CONTENT.featuresSection.eyebrow}</Eyebrow>
            <h2 className={`mt-4 max-w-3xl ${MK_H2}`}>{HOME_CONTENT.featuresSection.heading}</h2>
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-6 lg:gap-6">
            {features.map((f, i) => {
              const wide = i === features.length - 1;
              const art = FEATURE_ART[i];
              return (
                <Reveal
                  key={f.title}
                  index={i % 3}
                  className={`${FEATURE_SPANS[i] ?? "lg:col-span-2"} ${wide ? "sm:col-span-2" : ""}`}
                >
                  <Panel
                    data-testid="home-feature-item"
                    className={`group flex h-full flex-col p-7 transition-colors duration-300 hover:border-[var(--carbon)]/25 sm:p-8 ${
                      wide ? "lg:flex-row lg:items-center lg:gap-10" : ""
                    }`}
                  >
                    <div className={wide ? "lg:w-1/3" : "max-w-md"}>
                      <p className={MK_INDEX}>{String(i + 1).padStart(2, "0")}</p>
                      <h3 className={`mt-4 ${MK_H3}`}>{f.title}</h3>
                      <p className={`mt-3 ${MK_BODY}`}>{f.body}</p>
                    </div>
                    {art && (
                      <Art
                        src={art}
                        width={1200}
                        height={800}
                        className={`mx-auto my-4 h-52 w-full object-contain transition-transform sm:object-cover duration-700 ease-out group-hover:scale-[1.04] ${
                          i < 2 ? "sm:h-72" : "sm:h-56"
                        } ${wide ? "lg:my-0 lg:w-1/3" : ""}`}
                      />
                    )}
                    <Ledger
                      label={f.ledger}
                      facts={f.facts}
                      className={wide ? "w-full lg:w-1/3" : "mt-auto w-full"}
                    />
                  </Panel>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* Credit engine spotlight — carbon band; the three phases sit under the
          three pedestals in the artwork. */}
      <section className="bg-[var(--carbon)] py-20 text-white sm:py-28" data-testid="home-engine">
        <div className={MK_WRAP}>
          <Reveal>
            <Eyebrow tone="dark">{engine.eyebrow}</Eyebrow>
            <p className={`mt-5 max-w-4xl ${MK_STATEMENT}`}>
              {engine.lead} <span className="text-white/60">{engine.rest}</span>
            </p>
          </Reveal>
          <Reveal index={1} className="mx-auto mt-6 max-w-[1040px]">
            <div className="aspect-[16/7] overflow-hidden">
              <Art
                src={engineArt}
                width={1536}
                height={864}
                tone="dark"
                className="h-full w-full object-cover object-[center_72%]"
              />
            </div>
            <ol className="grid gap-8 sm:grid-cols-3 sm:gap-6">
              {engine.phases.map((phase, i) => (
                <li key={phase.title} className="border-t border-white/15 pt-5 sm:text-center">
                  <span className={`${MK_MONO} text-xs tabular-nums text-white/60`}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className={`mt-3 ${MK_H4}`}>{phase.title}</h3>
                  <p className="mx-auto mt-2 max-w-xs text-base leading-relaxed text-white/60">
                    {phase.body}
                  </p>
                  <p
                    className={`${MK_MONO} mt-4 inline-flex items-center gap-2 rounded border border-white/15 px-2 py-1 text-xs tabular-nums`}
                  >
                    <span className="text-white/60">{phase.fact.label}</span>
                    <span className={i === 1 ? "text-[var(--lime)]" : "text-white"}>
                      {phase.fact.value}
                    </span>
                  </p>
                </li>
              ))}
            </ol>
          </Reveal>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 py-20 sm:py-28">
        <div className={MK_WRAP}>
          <Reveal>
            <Eyebrow>{HOME_CONTENT.stepsSection.eyebrow}</Eyebrow>
            <h2 className={`mt-4 max-w-3xl ${MK_H2}`}>{HOME_CONTENT.stepsSection.heading}</h2>
          </Reveal>
          <ol className="mt-10 grid gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((s, i) => {
              const art = STEP_ART[i];
              return (
                <li key={s.title}>
                  <Reveal index={i} className="group">
                    {art && (
                      <Art
                        src={art}
                        width={900}
                        height={600}
                        className="mb-6 h-40 w-full object-contain transition-transform duration-700 ease-out group-hover:-translate-y-1.5"
                      />
                    )}
                    <div className="border-t border-[var(--carbon)] pt-5">
                      <span className={MK_INDEX}>{String(i + 1).padStart(2, "0")}</span>
                      <h3 className={`mt-5 ${MK_H4}`}>{s.title}</h3>
                      <p className={`mt-2 ${MK_BODY}`}>{s.body}</p>
                    </div>
                  </Reveal>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-20 border-t border-[var(--mk-hair)] py-20 sm:py-28">
        <Reveal className={`${MK_WRAP} grid gap-10 lg:grid-cols-[2fr_3fr] lg:gap-16`}>
          <div>
            <h2 className={MK_H2}>{HOME_CONTENT.faqSection.heading}</h2>
            <p className={`mt-4 max-w-sm ${MK_BODY}`}>{HOME_CONTENT.faqSection.description}</p>
            <Art
              src={faqArt}
              width={900}
              height={600}
              className="mt-8 h-52 w-64 object-cover max-lg:hidden"
            />
          </div>
          <div className="border-t border-[var(--mk-hair)]">
            {faqs.map((f) => (
              <FaqItem key={f.q} q={f.q} a={f.a} />
            ))}
          </div>
        </Reveal>
      </section>

      {/* Closing CTA — carbon band that runs into the dark footer */}
      <section className="relative overflow-hidden bg-[var(--carbon)] text-white">
        <Art
          src={closingArt}
          width={1536}
          height={656}
          tone="dark"
          className="absolute inset-y-0 right-0 h-full w-auto max-w-none object-cover opacity-50 lg:opacity-100"
        />
        <div className={`${MK_WRAP} relative border-b border-white/10 py-20 sm:py-28`}>
          <Reveal>
            <h2 className="max-w-4xl text-[36px] leading-[1.05] tracking-[-0.025em] sm:text-[56px]">
              {closing.heading}
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-snug text-white/60">
              {closing.description}
            </p>
            <MkButton
              to={primaryHref}
              size="lg"
              onClick={() => track(EVENTS.cta_clicked, { cta: "primary", location: "footer_band" })}
              data-testid="home-bottom-cta-link"
              className="mt-9"
            >
              {user ? closing.signedInLabel : closing.signedOutLabel}
            </MkButton>
          </Reveal>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
