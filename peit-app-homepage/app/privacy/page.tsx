import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Header } from '@/components/header'

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto">
          <Button variant="ghost" size="sm" asChild className="mb-6">
            <Link href="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Home
            </Link>
          </Button>

          <article className="prose dark:prose-invert max-w-none">
            <h1>Privacy Policy</h1>
            <p className="text-muted-foreground">Last updated: December 22, 2025</p>

            <h2>1. Overview</h2>
            <p>
              PEIT Map Creator ("we", "our", or "the Service") is committed to protecting your
              privacy. This Privacy Policy explains what information we collect, how we use it,
              and your rights regarding your data.
            </p>

            <h2>2. Information We Collect</h2>

            <h3>2.1 Account Information</h3>
            <p>When you create an account, we collect:</p>
            <ul>
              <li>
                <strong>Email address</strong> - Used for account authentication and optional
                notifications
              </li>
              <li>
                <strong>OAuth profile data</strong> - If you sign in with Google or GitHub, we
                receive your name and profile picture from those services
              </li>
            </ul>

            <h3>2.2 Uploaded Files</h3>
            <p>
              When you upload geospatial files (GeoJSON, Shapefile, KML, GeoPackage, etc.), we
              temporarily process them to generate your environmental maps. Uploaded files are:
            </p>
            <ul>
              <li>Processed on secure servers</li>
              <li>Not shared with third parties</li>
              <li>Deleted after processing completes</li>
            </ul>

            <h3>2.3 Generated Content</h3>
            <p>Maps and reports you generate are stored for <strong>7 days</strong>, including:</p>
            <ul>
              <li>Interactive HTML maps</li>
              <li>PDF and Excel reports</li>
              <li>Project names and IDs you provide</li>
            </ul>

            <h3>2.4 Usage Data</h3>
            <p>We automatically collect:</p>
            <ul>
              <li>
                <strong>IP addresses</strong> - Used for rate limiting to prevent abuse (stored
                temporarily)
              </li>
              <li>
                <strong>Job metadata</strong> - Timestamps, feature counts, and processing status
              </li>
            </ul>

            <h2>3. How We Use Your Information</h2>
            <p>We use collected information to:</p>
            <ul>
              <li>Provide and operate the Service</li>
              <li>Authenticate your account</li>
              <li>Generate environmental maps from your uploaded files</li>
              <li>Prevent abuse through rate limiting</li>
              <li>Improve the Service based on usage patterns</li>
            </ul>

            <h2>4. Data Storage and Security</h2>

            <h3>4.1 Where Your Data is Stored</h3>
            <p>We use the following third-party services to operate:</p>
            <ul>
              <li>
                <strong>Supabase</strong> - Account authentication and job history database
              </li>
              <li>
                <strong>Modal</strong> - Serverless computing for file processing
              </li>
              <li>
                <strong>Vercel</strong> - Web hosting and map storage (Vercel Blob)
              </li>
            </ul>
            <p>
              All services use industry-standard security practices. Data is transmitted over
              encrypted connections (HTTPS).
            </p>

            <h3>4.2 Data Retention</h3>
            <ul>
              <li>
                <strong>Account data</strong> - Retained until you delete your account
              </li>
              <li>
                <strong>Generated maps and reports</strong> - Automatically deleted after 7 days
              </li>
              <li>
                <strong>Uploaded files</strong> - Deleted immediately after processing
              </li>
              <li>
                <strong>Rate limit data</strong> - Reset daily
              </li>
            </ul>

            <h2>5. Data Sharing</h2>
            <p>
              <strong>We do not sell your data.</strong> We do not share your personal information
              with third parties except:
            </p>
            <ul>
              <li>
                With service providers necessary to operate the Service (listed in Section 4.1)
              </li>
              <li>If required by law or to protect our legal rights</li>
            </ul>

            <h2>6. Generated Map Visibility</h2>
            <p>
              Maps you generate are accessible via unique URLs. These URLs are:
            </p>
            <ul>
              <li>
                <strong>Unlisted</strong> - Not indexed by search engines
              </li>
              <li>
                <strong>Not private</strong> - Anyone with the link can view the map
              </li>
            </ul>
            <p>
              If you share a map URL, the recipient can view all data in that map. Do not share
              URLs if your project data is confidential.
            </p>

            <h2>7. Cookies and Tracking</h2>
            <p>We use minimal cookies:</p>
            <ul>
              <li>
                <strong>Authentication cookies</strong> - Essential for keeping you signed in
              </li>
              <li>
                <strong>Theme preference</strong> - Remembers your light/dark mode choice
              </li>
            </ul>
            <p>
              We do not use advertising trackers or sell data to advertisers.
            </p>

            <h2>8. Your Rights</h2>
            <p>You have the right to:</p>
            <ul>
              <li>
                <strong>Access your data</strong> - View your job history in the dashboard
              </li>
              <li>
                <strong>Delete your data</strong> - Delete individual jobs or your entire account
                in Account Settings
              </li>
              <li>
                <strong>Export your data</strong> - Download your generated maps and reports
              </li>
            </ul>
            <p>
              Account deletion permanently removes your profile and job history. Generated maps
              stored in Vercel Blob will be deleted with your account or expire after 7 days,
              whichever comes first.
            </p>

            <h2>9. Children's Privacy</h2>
            <p>
              The Service is not intended for users under 13 years of age. We do not knowingly
              collect information from children under 13.
            </p>

            <h2>10. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. Continued use of the Service
              after changes constitutes acceptance. We encourage you to review this page
              periodically.
            </p>

            <h2>11. Contact</h2>
            <p>
              If you have questions about this Privacy Policy or your data, please visit our{' '}
              <a
                href="https://github.com/lukaskucinski/peit_map_creator"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                GitHub repository
              </a>{' '}
              to open an issue or discussion.
            </p>
          </article>
        </div>
      </main>
    </div>
  )
}

export const metadata = {
  title: 'Privacy Policy - PEIT Map Creator',
  description: 'Privacy Policy for PEIT Map Creator. Learn how we collect, use, and protect your data.',
}
