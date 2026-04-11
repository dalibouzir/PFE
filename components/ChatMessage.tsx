export function ChatMessage({ role, text }: { role: "user" | "assistant"; text: string }) {
  const isUser = role === "user";
  return (
    <div className={`my-2 rounded-lg p-3 ${isUser ? "bg-brand-700 text-white" : "bg-white ring-1 ring-black/10"}`}>
      <p className="text-xs uppercase opacity-70">{role}</p>
      <p>{text}</p>
    </div>
  );
}
