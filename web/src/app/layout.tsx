import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "lazyJobFinder - Panel de Administración",
  description: "Interfaz sobria, funcional y local para el control del pipeline de búsqueda de empleo.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className={`${inter.className} min-h-screen bg-background text-foreground flex flex-col md:flex-row`}>
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto p-4 md:p-8 max-w-7xl">
          {children}
        </main>
      </body>
    </html>
  );
}
