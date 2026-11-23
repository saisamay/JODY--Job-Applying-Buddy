import type { Metadata } from "next";
import "@fontsource-variable/dm-sans/wght.css";
import "@fontsource/instrument-serif/latin-400-italic.css";
import "./globals.css";
export const metadata: Metadata = {
  title: "JODY · Your AI Job Applying Buddy",
  description:
    "Find roles that fit your experience and prepare applications in your private workspace.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main-content">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
