import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BroPilot",
  description: "A safe multi-agent PR builder for reviewable code changes.",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
