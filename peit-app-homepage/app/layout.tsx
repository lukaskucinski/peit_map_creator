import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { Analytics } from "@vercel/analytics/next"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  metadataBase: new URL("https://peit-map-creator.vercel.app"),
  title: "PEIT Map Creator",
  description: "Upload, process, and visualize geospatial files in seconds.",
  generator: "v0.app",
  icons: {
    icon: [
      {
        url: "/icon-light-48x48.png",
        sizes: "48x48",
        media: "(prefers-color-scheme: light)",
      },
      {
        url: "/icon-dark-48x48.png",
        sizes: "48x48",
        media: "(prefers-color-scheme: dark)",
      },
      {
        url: "/icon.svg",
        type: "image/svg+xml",
      },
    ],
  },
  openGraph: {
    title: "PEIT Map Creator - Permitting and Environmental Information Tool",
    description: "Upload, process, and visualize geospatial files in seconds.",
    url: "https://peit-map-creator.vercel.app",
    siteName: "PEIT Map Creator",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "PEIT Map Creator",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "PEIT Map Creator",
    description: "Upload, process, and visualize geospatial files in seconds.",
    images: ["/og-image.png"],
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`font-sans antialiased ${inter.className}`}>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
