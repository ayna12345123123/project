import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col px-6 py-10 md:px-10">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-lg bg-accent text-accent-foreground">
            <span className="font-bold">L</span>
          </span>
          <span className="text-lg font-semibold tracking-tight">Linkforge</span>
        </Link>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm">{children}</div>
        </div>
      </div>
      <div className="relative hidden lg:block">
        <div className="absolute inset-0 bg-gradient-to-br from-accent via-fuchsia-500 to-cyan-500" />
        <div className="grid-bg absolute inset-0 mix-blend-overlay opacity-60" />
        <div className="relative flex h-full flex-col justify-end p-10 text-white">
          <p className="max-w-md text-balance text-2xl font-medium leading-relaxed">
            “The only link-in-bio tool I&apos;ve used that takes performance,
            analytics and security as seriously as I do.”
          </p>
          <p className="mt-4 text-sm opacity-80">— Maya R., indie maker · 38k followers</p>
        </div>
      </div>
    </div>
  );
}
