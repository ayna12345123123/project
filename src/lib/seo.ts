import type { Metadata } from "next";
import { env } from "./env";

export interface SeoInput {
  title: string;
  description?: string | null;
  image?: string | null;
  canonical?: string;
  noIndex?: boolean;
}

export function buildMetadata({
  title,
  description,
  image,
  canonical,
  noIndex,
}: SeoInput): Metadata {
  const fullTitle = title.includes(env.APP_NAME) ? title : `${title} · ${env.APP_NAME}`;
  return {
    title: fullTitle,
    description: description ?? undefined,
    alternates: canonical ? { canonical } : undefined,
    robots: noIndex ? { index: false, follow: false } : undefined,
    openGraph: {
      title: fullTitle,
      description: description ?? undefined,
      url: canonical,
      siteName: env.APP_NAME,
      images: image ? [{ url: image }] : undefined,
      type: "website",
    },
    twitter: {
      card: image ? "summary_large_image" : "summary",
      title: fullTitle,
      description: description ?? undefined,
      images: image ? [image] : undefined,
    },
  };
}

export function jsonLdPerson(args: {
  name: string;
  url: string;
  image?: string | null;
  sameAs?: string[];
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Person",
    name: args.name,
    url: args.url,
    image: args.image ?? undefined,
    sameAs: args.sameAs?.length ? args.sameAs : undefined,
  };
}
