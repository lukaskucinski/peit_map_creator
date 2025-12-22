import Link from 'next/link'

export function Footer() {
  return (
    <footer className="border-t border-border bg-card py-4">
      <div className="container mx-auto px-4">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 text-sm text-muted-foreground">
          <span>&copy; {new Date().getFullYear()} PEIT Map Creator</span>
          <span className="hidden sm:inline">|</span>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="hover:text-foreground hover:underline">
              Terms of Service
            </Link>
            <Link href="/privacy" className="hover:text-foreground hover:underline">
              Privacy Policy
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
