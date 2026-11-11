"""Error-catalog contract tests.

The drift these catch: a slice grows a new AppError subclass but nobody adds
it to shared/errors.toml — so the frontend has no copy for it and users see
raw fallbacks. Both directions are enforced:

  exception -> catalog : every AppError subclass carries an internal_code
                         that exists in the generated ERROR_CODES, with a
                         matching HTTP status.
  catalog   -> files   : the generated artifacts are current
                         (`python3 scripts/gen_errors.py --check` in CI).

Importing app.main pulls in every feature slice, so __subclasses__ walking
sees all domain errors without per-slice imports here.
"""

import app.main  # noqa: F401  -- forces every feature slice (and its domain errors) to load
from app.core.error_codes import ERROR_CODES
from app.core.exceptions import AppError


def _all_error_classes() -> list[type[AppError]]:
    seen: list[type[AppError]] = [AppError]
    queue = [AppError]
    while queue:
        for sub in queue.pop().__subclasses__():
            seen.append(sub)
            queue.append(sub)
    return seen


def test_every_error_class_maps_to_the_catalog():
    unmapped = [
        cls.__name__ for cls in _all_error_classes() if cls.internal_code not in ERROR_CODES
    ]
    assert not unmapped, (
        f"Error classes missing from shared/errors.toml: {unmapped}. "
        "Add a catalog entry and run `python3 scripts/gen_errors.py`."
    )


def test_error_class_status_matches_catalog():
    mismatched = [
        f"{cls.__name__}: class={cls.status_code} "
        f"catalog={ERROR_CODES[cls.internal_code]['status']}"
        for cls in _all_error_classes()
        if cls.status_code != ERROR_CODES[cls.internal_code]["status"]
    ]
    assert not mismatched, f"status_code / catalog status drift: {mismatched}"


def test_catalog_codes_follow_the_naming_convention():
    bad = [code for code in ERROR_CODES if not code.startswith("ERR_") or len(code.split("_")) != 3]
    assert not bad, f"Malformed codes (expected ERR_<DOMAIN>_<NNN>): {bad}"
