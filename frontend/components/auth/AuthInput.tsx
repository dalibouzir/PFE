import type { InputHTMLAttributes } from "react";

type AuthInputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
};

export function AuthInput({ label, type = "text", ...props }: AuthInputProps) {
  return (
    <label className="block space-y-2 text-sm font-medium text-white/82">
      <span>{label}</span>
      <input
        type={type}
        {...props}
        className="auth-input soft-focus w-full rounded-xl px-4 py-3 text-sm text-white placeholder:text-white/55"
      />
    </label>
  );
}
