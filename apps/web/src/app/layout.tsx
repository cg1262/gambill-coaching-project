import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark-premium">
      <body style={{ fontFamily: "Inter, Arial, sans-serif" }}>{children}</body>
    </html>
  );
}
