export function ChatMessage({ role, text }: { role: "user" | "assistant"; text: string }) {
  const isUser = role === "user";
  return (
    <div className={`my-2 rounded-xl p-3 ${isUser ? "bg-[var(--primary)] text-white" : "bg-[var(--surface)] ring-1 ring-[var(--line)]"}`}>
      <p className="text-xs uppercase opacity-70">{role}</p>
      <p>{text}</p>
    </div>
  );
}
