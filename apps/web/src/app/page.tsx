export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col items-center gap-4 px-8 py-24 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
          FORGE
        </h1>
        <p className="text-base text-zinc-600 dark:text-zinc-400">
          Enterprise AI Deployment &amp; Decision Platform
        </p>
        <p className="text-sm text-zinc-500 dark:text-zinc-500">
          Foundation phase — dashboard, investigations, and evaluation views
          land in later phases.
        </p>
      </main>
    </div>
  );
}
