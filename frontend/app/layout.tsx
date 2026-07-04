import "./globals.css";

export const metadata = {
  title: "Visibility Docs AI",
  description: "Enterprise Document Intelligence Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
