import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Header } from '@/components/header'
import { Footer } from '@/components/footer'

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <main className="container mx-auto px-4 py-8 flex-1">
        <div className="max-w-3xl mx-auto">
          <Button variant="ghost" size="sm" asChild className="mb-6">
            <Link href="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Home
            </Link>
          </Button>

          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight mb-2">Privacy Policy</h1>
            <p className="text-muted-foreground">Last updated: December 22, 2025</p>
          </div>

          {/* Quick Summary */}
          <div className="bg-muted/50 border rounded-lg p-4 mb-8">
            <p className="text-sm text-muted-foreground">
              <strong className="text-foreground">Summary:</strong> We collect only what&apos;s needed to provide the service.
              Your uploaded files are processed and deleted. Generated maps are stored for 7 days and are accessible via
              unique URLs (unlisted but not private). We do not sell your data.
            </p>
          </div>

          {/* Sections */}
          <div className="space-y-8">

            {/* Section 1 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">1. Overview</h2>
              <p className="text-muted-foreground leading-relaxed">
                PEIT Map Creator (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;the Service&rdquo;) is committed to protecting your
                privacy. This Privacy Policy explains what information we collect, how we use it,
                and your rights regarding your data.
              </p>
            </section>

            {/* Section 2 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">2. Information We Collect</h2>

              <div className="space-y-6">
                {/* 2.1 */}
                <div className="pl-4 border-l-2 border-muted">
                  <h3 className="text-base font-medium mb-2">2.1 Account Information</h3>
                  <p className="text-muted-foreground text-sm mb-2">When you create an account, we collect:</p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-2">
                    <li><strong className="text-foreground">Email address</strong> — Used for account authentication</li>
                    <li><strong className="text-foreground">OAuth profile data</strong> — Name and profile picture from Google or GitHub</li>
                  </ul>
                </div>

                {/* 2.2 */}
                <div className="pl-4 border-l-2 border-muted">
                  <h3 className="text-base font-medium mb-2">2.2 Uploaded Files</h3>
                  <p className="text-muted-foreground text-sm mb-2">
                    When you upload geospatial files (GeoJSON, Shapefile, KML, GeoPackage, etc.), we temporarily process them. Uploaded files are:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-2">
                    <li>Processed on secure servers</li>
                    <li>Not shared with third parties</li>
                    <li>Deleted after processing completes</li>
                  </ul>
                </div>

                {/* 2.3 */}
                <div className="pl-4 border-l-2 border-muted">
                  <h3 className="text-base font-medium mb-2">2.3 Generated Content</h3>
                  <p className="text-muted-foreground text-sm mb-2">
                    Maps and reports you generate are stored for <strong className="text-foreground">7 days</strong>, including:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-2">
                    <li>Interactive HTML maps</li>
                    <li>PDF and Excel reports</li>
                    <li>Project names and IDs you provide</li>
                  </ul>
                </div>

                {/* 2.4 */}
                <div className="pl-4 border-l-2 border-muted">
                  <h3 className="text-base font-medium mb-2">2.4 Usage Data</h3>
                  <p className="text-muted-foreground text-sm mb-2">We automatically collect:</p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-2">
                    <li><strong className="text-foreground">IP addresses</strong> — Used for rate limiting (stored temporarily)</li>
                    <li><strong className="text-foreground">Job metadata</strong> — Timestamps, feature counts, processing status</li>
                  </ul>
                </div>
              </div>
            </section>

            {/* Section 3 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">3. How We Use Your Information</h2>
              <p className="text-muted-foreground leading-relaxed mb-3">We use collected information to:</p>
              <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-2">
                <li>Provide and operate the Service</li>
                <li>Authenticate your account</li>
                <li>Generate environmental maps from your uploaded files</li>
                <li>Prevent abuse through rate limiting</li>
                <li>Improve the Service based on usage patterns</li>
              </ul>
            </section>

            {/* Section 4 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">4. Data Storage and Security</h2>

              <div className="space-y-6">
                {/* 4.1 */}
                <div className="pl-4 border-l-2 border-muted">
                  <h3 className="text-base font-medium mb-2">4.1 Third-Party Services</h3>
                  <p className="text-muted-foreground text-sm mb-2">We use the following services to operate:</p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground text-sm ml-2">
                    <li><strong className="text-foreground">Supabase</strong> — Account authentication and job history database</li>
                    <li><strong className="text-foreground">Modal</strong> — Serverless computing for file processing</li>
                    <li><strong className="text-foreground">Vercel</strong> — Web hosting and map storage</li>
                  </ul>
                  <p className="text-muted-foreground text-sm mt-2">
                    All services use industry-standard security. Data is transmitted over encrypted connections (HTTPS).
                  </p>
                </div>

                {/* 4.2 */}
                <div className="pl-4 border-l-2 border-muted">
                  <h3 className="text-base font-medium mb-2">4.2 Data Retention</h3>
                  <div className="bg-muted/30 rounded-lg p-3">
                    <ul className="space-y-2 text-sm">
                      <li className="flex justify-between">
                        <span className="text-muted-foreground">Account data</span>
                        <span className="font-medium">Until you delete your account</span>
                      </li>
                      <li className="flex justify-between">
                        <span className="text-muted-foreground">Generated maps & reports</span>
                        <span className="font-medium">7 days</span>
                      </li>
                      <li className="flex justify-between">
                        <span className="text-muted-foreground">Uploaded files</span>
                        <span className="font-medium">Deleted after processing</span>
                      </li>
                      <li className="flex justify-between">
                        <span className="text-muted-foreground">Rate limit data</span>
                        <span className="font-medium">Reset daily</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </section>

            {/* Section 5 - Important callout */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">5. Data Sharing</h2>
              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4 mb-3">
                <p className="text-sm">
                  <strong className="text-green-600 dark:text-green-400">We do not sell your data.</strong> We do not share
                  your personal information with third parties for marketing purposes.
                </p>
              </div>
              <p className="text-muted-foreground leading-relaxed mb-2">We only share data:</p>
              <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-2">
                <li>With service providers necessary to operate the Service (listed in Section 4.1)</li>
                <li>If required by law or to protect our legal rights</li>
              </ul>
            </section>

            {/* Section 6 - Important callout */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">6. Generated Map Visibility</h2>
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 mb-3">
                <p className="text-sm">
                  <strong className="text-amber-600 dark:text-amber-400">Important:</strong> Maps are{' '}
                  <strong>unlisted</strong> (not indexed by search engines) but{' '}
                  <strong>not private</strong>—anyone with the link can view the map.
                </p>
              </div>
              <p className="text-muted-foreground leading-relaxed">
                If you share a map URL, the recipient can view all data in that map. Do not share
                URLs if your project data is confidential.
              </p>
            </section>

            {/* Section 7 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">7. Cookies and Tracking</h2>
              <p className="text-muted-foreground leading-relaxed mb-3">We use minimal cookies:</p>
              <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-2 mb-3">
                <li><strong className="text-foreground">Authentication cookies</strong> — Essential for keeping you signed in</li>
                <li><strong className="text-foreground">Theme preference</strong> — Remembers your light/dark mode choice</li>
              </ul>
              <p className="text-muted-foreground leading-relaxed">
                We do not use advertising trackers or sell data to advertisers.
              </p>
            </section>

            {/* Section 8 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">8. Your Rights</h2>
              <p className="text-muted-foreground leading-relaxed mb-3">You have the right to:</p>
              <div className="grid gap-3 sm:grid-cols-3 mb-4">
                <div className="bg-muted/30 rounded-lg p-3 text-center">
                  <p className="font-medium text-sm mb-1">Access</p>
                  <p className="text-xs text-muted-foreground">View your job history in the dashboard</p>
                </div>
                <div className="bg-muted/30 rounded-lg p-3 text-center">
                  <p className="font-medium text-sm mb-1">Delete</p>
                  <p className="text-xs text-muted-foreground">Delete jobs or your entire account</p>
                </div>
                <div className="bg-muted/30 rounded-lg p-3 text-center">
                  <p className="font-medium text-sm mb-1">Export</p>
                  <p className="text-xs text-muted-foreground">Download your maps and reports</p>
                </div>
              </div>
              <p className="text-muted-foreground leading-relaxed text-sm">
                Account deletion permanently removes your profile and job history. Generated maps
                will be deleted with your account or expire after 7 days, whichever comes first.
              </p>
            </section>

            {/* Section 9 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">9. Children&apos;s Privacy</h2>
              <p className="text-muted-foreground leading-relaxed">
                The Service is not intended for users under 13 years of age. We do not knowingly
                collect information from children under 13.
              </p>
            </section>

            {/* Section 10 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">10. Changes to This Policy</h2>
              <p className="text-muted-foreground leading-relaxed">
                We may update this Privacy Policy from time to time. Continued use of the Service
                after changes constitutes acceptance. We encourage you to review this page periodically.
              </p>
            </section>

            {/* Section 11 */}
            <section>
              <h2 className="text-xl font-semibold mb-3 pb-2 border-b">11. Contact</h2>
              <p className="text-muted-foreground leading-relaxed">
                If you have questions about this Privacy Policy or your data, please visit our{' '}
                <a
                  href="https://github.com/lukaskucinski/peit_map_creator"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline font-medium"
                >
                  GitHub repository
                </a>{' '}
                to open an issue or discussion.
              </p>
            </section>

          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}

export const metadata = {
  title: 'Privacy Policy - PEIT Map Creator',
  description: 'Privacy Policy for PEIT Map Creator. Learn how we collect, use, and protect your data.',
}
