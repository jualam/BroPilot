import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BroPilot Workbench",
  description: "Review-ready AI workflows for high-trust automation.",
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
