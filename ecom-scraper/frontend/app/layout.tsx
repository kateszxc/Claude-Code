import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "E-com Brand Scraper",
  description: "Find e-commerce brands by niche, location and age – export founders, emails and growth ideas to CSV.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
