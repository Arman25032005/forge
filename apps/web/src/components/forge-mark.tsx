export function ForgeMark({ size = 40 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-2xl bg-gradient-to-br from-accent to-accent-hover shadow-lg shadow-accent/20"
      style={{ width: size, height: size }}
    >
      <svg
        width={size * 0.55}
        height={size * 0.55}
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--accent-fg)"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
      </svg>
    </div>
  );
}

export function ForgeWordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <ForgeMark size={28} />
      <span className="text-base font-semibold tracking-tight text-fg">Forge</span>
    </div>
  );
}
