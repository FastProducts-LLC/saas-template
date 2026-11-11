import type { PasswordRules as Rules } from "../model/password-policy";
import { PASSWORD_MIN_LENGTH } from "../model/password-policy";

function PasswordRule({ ruleKey, met, label }: { ruleKey: string; met: boolean; label: string }) {
  return (
    <li
      data-testid="password-rule"
      data-id={ruleKey}
      data-met={met}
      className={`flex items-center gap-2 text-xs ${met ? "text-[var(--success)]" : "text-[var(--slate)]/55"}`}
    >
      <span
        className={`flex h-3.5 w-3.5 items-center justify-center rounded-full text-[9px] text-white ${
          met ? "bg-[var(--success)]" : "bg-[var(--slate)]/30"
        }`}
      >
        {met ? "✓" : ""}
      </span>
      {label}
    </li>
  );
}

export default function PasswordRules({ rules }: { rules: Rules }) {
  return (
    <ul className="space-y-1" data-testid="password-rules">
      <PasswordRule
        ruleKey="length"
        met={rules.length}
        label={`At least ${PASSWORD_MIN_LENGTH} characters`}
      />
      <PasswordRule ruleKey="mix" met={rules.mix} label="Mix of letters and numbers" />
      <PasswordRule
        ruleKey="notCommon"
        met={rules.notCommon}
        label="Not a commonly used password"
      />
    </ul>
  );
}
