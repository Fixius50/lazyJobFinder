import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "@/app/globals.css";
import { Toaster } from "sonner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "lazyJobFinder - Panel de Control Unificado",
  description: "Interfaz moderna, local y fluida para la búsqueda y evaluación autónoma de empleo.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className={`${inter.className} min-h-[100dvh] bg-background text-foreground flex flex-col antialiased selection:bg-primary/20 selection:text-primary`}>
        {children}
        <Toaster richColors position="top-right" theme="dark" closeButton />
      </body>
    </html>
  );
}
