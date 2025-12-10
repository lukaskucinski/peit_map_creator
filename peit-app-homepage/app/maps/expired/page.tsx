import Link from 'next/link'
import { Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function MapExpiredPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center max-w-md mx-auto p-8">
        <div className="mb-6 flex justify-center">
          <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
            <Clock className="h-8 w-8 text-muted-foreground" />
          </div>
        </div>

        <h1 className="text-2xl font-bold mb-2">Map Expired</h1>

        <p className="text-muted-foreground mb-6">
          This map link has expired or is invalid. Maps are available for 7 days after creation.
        </p>

        <Button asChild>
          <Link href="/">
            Create a New Map
          </Link>
        </Button>
      </div>
    </div>
  )
}

export const metadata = {
  title: 'Map Expired - PEIT Map Creator',
  description: 'This map link has expired. Create a new map with PEIT Map Creator.',
}
