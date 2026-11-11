// ESLint 9 flat config — type-aware rules are intentionally off (tsc already
// runs in `npm run build`); this catches logic/hooks mistakes, not types.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Vite HMR works best when component files export only components;
      // warn (not error) because context/provider files legitimately mix.
      "react-refresh/only-export-components": [
        "warn",
        {
          allowConstantExport: true,
          allowExportNames: ["useAuth", "useOrg"],
        },
      ],
      // The API layer normalizes unknown errors — `any` shows up at those
      // boundaries deliberately; keep it visible but not blocking.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
);
