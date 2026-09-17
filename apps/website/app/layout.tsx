import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
const sans = Geist({ subsets: ["latin"], variable: "--font-geist" });
const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-instrument-serif",
});
const mono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});
export const metadata: Metadata = {
  title: "gpu-postal · Experimental US address parser",
  description:
    "Experimental US address parsing with a tiny WebGPU model. Labels address components in context, locally in your browser.",
};
export const viewport: Viewport = { themeColor: "#111111" };

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`dark scheme-dark scroll-pt-6 font-sans ${sans.variable} ${mono.variable} ${serif.variable}`}
    >
      <body className="bg-background text-base leading-6 font-normal text-foreground antialiased selection:bg-primary selection:text-background **:motion-reduce:transition-none **:motion-reduce:animate-none [&_a]:decoration-wavy [&_a]:decoration-1 [&_a]:underline-offset-4 [&_a:hover]:text-foreground [&_a:hover]:underline [&_a:focus-visible]:outline-2 [&_a:focus-visible]:outline-offset-5 [&_a:focus-visible]:outline-primary [&_button]:touch-manipulation [&_button:not(:disabled)]:cursor-pointer">
        {children}
      </body>
    </html>
  );
}
