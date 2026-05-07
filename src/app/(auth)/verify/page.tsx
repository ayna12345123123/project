export const metadata = { title: "Check your email" };

export default function VerifyPage() {
  return (
    <div className="space-y-3 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Check your email</h1>
      <p className="text-sm text-muted-foreground">
        We sent a magic link to your inbox. Click the link to finish signing in.
      </p>
    </div>
  );
}
