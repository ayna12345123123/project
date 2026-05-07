/* eslint-disable no-console */
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

const RESERVED = [
  "admin",
  "api",
  "auth",
  "login",
  "logout",
  "register",
  "signup",
  "signin",
  "dashboard",
  "settings",
  "pricing",
  "support",
  "help",
  "terms",
  "privacy",
  "blog",
  "u",
  "user",
  "users",
  "static",
  "_next",
  "favicon.ico",
  "robots.txt",
  "sitemap.xml",
  "well-known",
  "linkforge",
  "together",
  "kebruni",
];

const TEMPLATES = [
  {
    key: "minimal-light",
    name: "Minimal · Light",
    description: "Clean, light card layout with rounded buttons.",
    isPro: false,
    blocksJson: [
      { type: "AVATAR", content: { src: null } },
      { type: "HEADER", content: { title: "Your name", subtitle: "@yourhandle" } },
      { type: "LINK", label: "Open my website", url: "https://example.com" },
      { type: "LINK", label: "Latest project", url: "https://example.com/project" },
      { type: "SOCIAL", content: { items: [] } },
    ],
    themeJson: {
      preset: "minimal-light",
      background: "#FAFAFA",
      surface: "#FFFFFF",
      text: "#0A0A0A",
      accent: "#111111",
      radius: 16,
      font: "Inter",
    },
  },
  {
    key: "neon-night",
    name: "Neon · Night",
    description: "Glassmorphism with a bold gradient backdrop.",
    isPro: true,
    blocksJson: [],
    themeJson: {
      preset: "neon-night",
      background: "linear-gradient(135deg,#7c3aed,#06b6d4)",
      surface: "rgba(255,255,255,0.08)",
      text: "#FFFFFF",
      accent: "#A78BFA",
      radius: 20,
      font: "Sora",
    },
  },
];

async function main() {
  console.log("[seed] reserved slugs…");
  for (const slug of RESERVED) {
    await prisma.reservedSlug.upsert({
      where: { slug },
      update: {},
      create: { slug, reason: "system reserved" },
    });
  }

  console.log("[seed] page templates…");
  for (const tpl of TEMPLATES) {
    await prisma.pageTemplate.upsert({
      where: { key: tpl.key },
      update: tpl,
      create: tpl,
    });
  }

  console.log("[seed] feature flags…");
  for (const [key, enabled] of [
    ["ai", true],
    ["billing", false],
    ["custom_domains", false],
    ["ab_testing", false],
  ] as const) {
    await prisma.featureFlag.upsert({
      where: { key },
      update: {},
      create: { key, enabled },
    });
  }

  console.log("[seed] done.");
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
