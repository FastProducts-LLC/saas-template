import Spinner from "./Spinner";

export default function FullScreenSpinner() {
  return (
    <div
      data-testid="fullscreen-spinner"
      className="flex min-h-screen items-center justify-center gap-2 bg-[var(--paper)] text-sm text-[var(--slate)]"
    >
      <Spinner className="h-4 w-4 text-[var(--teal)]" />
      Loading…
    </div>
  );
}
