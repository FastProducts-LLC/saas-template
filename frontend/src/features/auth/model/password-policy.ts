// UX-only password policy for instant feedback; the backend checks a fuller list.
// PASSWORD_MIN_LENGTH is generated from shared/policy.toml (gen_policy.py), so
// this mirror can't drift from the backend check (docs/customization.md § Security).

import { PASSWORD_MIN_LENGTH } from "../../../shared/lib/policy";

export { PASSWORD_MIN_LENGTH };

const COMMON_PASSWORDS =
  /^(password|password1|password123|12345678|123456789|qwerty123|abc12345|letmein1|welcome1|monkey123|dragon123|master123|iloveyou1)$/i;

export interface PasswordRules {
  length: boolean;
  mix: boolean;
  notCommon: boolean;
}

export function validatePassword(password: string): PasswordRules {
  return {
    length: password.length >= PASSWORD_MIN_LENGTH,
    mix: /[a-zA-Z]/.test(password) && /[0-9]/.test(password),
    notCommon: password.length > 0 && !COMMON_PASSWORDS.test(password),
  };
}

export const passwordMeetsRules = (rules: PasswordRules) =>
  rules.length && rules.mix && rules.notCommon;
