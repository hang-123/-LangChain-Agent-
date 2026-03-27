import { useState } from "react";

interface Props {
  onSend: (query: string) => Promise<void> | void;
  disabled?: boolean;
  placeholder?: string;
}

export function MessageInput({ onSend, disabled, placeholder }: Props) {
  const [value, setValue] = useState("");

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!value.trim() || disabled) return;
    await onSend(value.trim());
    setValue("");
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-auto rounded-2xl border border-slate-200 bg-white shadow-sm p-4"
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        rows={3}
        disabled={disabled}
        className="w-full resize-none bg-transparent outline-none text-slate-100 placeholder-slate-500"
      />
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
        <span>Shift + Enter 换行，Enter 提交</span>
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="px-5 py-1.5 rounded-full bg-accent text-slate-900 font-semibold disabled:opacity-40 transition hover:shadow-lg hover:shadow-emerald-500/30"
        >
          发送
        </button>
      </div>
    </form>
  );
}
