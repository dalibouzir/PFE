import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const config = [
  {
    ignores: [
      ".next/**",
      "next-env.d.ts",
      "node_modules/**",
      ".venv/**",
      ".venv*/**",
      "backend/.venv/**",
      "backend/.venv*/**",
      "backend/venv/**",
      "**/__pycache__/**",
      "**/.pytest_cache/**",
      "out/**",
      "dist/**",
      "coverage/**",
      "_archive/**",
      "scripts/capture_phase61_screenshots.js",
      "scripts/capture_phase62_screenshots.js",
    ],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default config;
