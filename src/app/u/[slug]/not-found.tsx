import Link from "next/link";

export default function PublicPageNotFound() {
  return (
    <div className="grid min-h-screen place-items-center px-4 text-center">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Page not found</h1>
        <p className="mt-2 text-muted-foreground">This Linkforge page doesn&apos;t exist or hasn&apos;t been published yet.</p>
        <Link href="/" className="mt-4 inline-block underline-offset-4 hover:underline">
          Go to homepage
        </Link>
      </div>
    </div>
  );
}
