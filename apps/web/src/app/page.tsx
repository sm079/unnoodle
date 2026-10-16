import Link from 'next/link';

export default function Home() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-4 px-6">
      <h1 className="text-3xl font-semibold">unnoodle</h1>
      <p className="text-muted-foreground">AI pictures and videos from one prompt box, without the wiring.</p>
      <Link href="/generate" className="underline underline-offset-4">
        Open the app
      </Link>
    </main>
  );
}
