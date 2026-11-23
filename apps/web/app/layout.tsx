import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "JODY · Job workspace",
  description: "Your private job search workspace.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
