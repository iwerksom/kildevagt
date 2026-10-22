import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kildevagt viewer",
  description: "A document beside its graph neighbourhood, with the source of every link.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <a href="/" className="brand">Kildevagt</a>
          <span className="muted">every link points back to the page it came from</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
