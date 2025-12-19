// Supabase Edge Function to send welcome emails via Resend
// Triggered by database trigger on auth.users INSERT

import "jsr:@supabase/functions-js/edge-runtime.d.ts"

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY")
const RESEND_ENDPOINT = "https://api.resend.com/emails"

// App constants
const APP_NAME = "PEIT Map Creator"
const APP_URL = "https://peit-map-creator.vercel.app"
const SENDER_EMAIL = "noreply@peit-map-creator.com"
const LOGO_URL = `${APP_URL}/logo_peit_map_creator.jpg`

// Generate styled HTML email
function generateWelcomeEmail(userName?: string): string {
  const greeting = userName ? `Hi ${userName},` : "Hi there,"

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to ${APP_NAME}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
  <table role="presentation" style="width: 100%; border-collapse: collapse;">
    <tr>
      <td style="padding: 40px 20px;">
        <table role="presentation" style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">

          <!-- Header with Logo -->
          <tr>
            <td style="padding: 32px 40px 24px; text-align: center; border-bottom: 1px solid #eaeaea;">
              <a href="${APP_URL}" target="_blank" style="text-decoration: none;">
                <img src="${LOGO_URL}" alt="${APP_NAME}" style="max-width: 180px; height: auto;" />
              </a>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 40px;">
              <h1 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: #1a1a1a; line-height: 1.3;">
                Welcome to ${APP_NAME}
              </h1>

              <p style="margin: 0 0 20px; font-size: 16px; color: #4a4a4a; line-height: 1.6;">
                ${greeting}
              </p>

              <p style="margin: 0 0 24px; font-size: 16px; color: #4a4a4a; line-height: 1.6;">
                Thanks for signing up! You now have access to:
              </p>

              <ul style="margin: 0 0 32px; padding-left: 24px; font-size: 16px; color: #4a4a4a; line-height: 1.8;">
                <li>Create more environmental maps</li>
                <li>Save maps to your account</li>
                <li>Access map history</li>
                <li>Download PDF/XLSX reports</li>
              </ul>

              <!-- CTA Button -->
              <table role="presentation" style="width: 100%;">
                <tr>
                  <td style="text-align: center; padding: 8px 0 24px;">
                    <a href="${APP_URL}" target="_blank" style="display: inline-block; padding: 14px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 500; border-radius: 6px;">
                      Start Creating
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin: 0; font-size: 16px; color: #4a4a4a; line-height: 1.6;">
                Happy mapping!
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 24px 40px; background-color: #fafafa; border-top: 1px solid #eaeaea; text-align: center;">
              <p style="margin: 0 0 8px; font-size: 14px; color: #888888;">
                &copy; ${new Date().getFullYear()} ${APP_NAME}
              </p>
              <a href="${APP_URL}" target="_blank" style="font-size: 14px; color: #2563eb; text-decoration: none;">
                ${APP_URL.replace('https://', '')}
              </a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
`
}

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
      },
    })
  }

  try {
    // Validate API key exists
    if (!RESEND_API_KEY) {
      console.error("RESEND_API_KEY is not set")
      return new Response(
        JSON.stringify({ error: "Email service not configured" }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      )
    }

    // Parse request body
    const { email, name } = await req.json()

    if (!email) {
      return new Response(
        JSON.stringify({ error: "Email is required" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      )
    }

    console.log(`Sending welcome email to: ${email}`)

    // Send email via Resend
    const response = await fetch(RESEND_ENDPOINT, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: `${APP_NAME} <${SENDER_EMAIL}>`,
        to: [email],
        subject: `Welcome to ${APP_NAME}`,
        html: generateWelcomeEmail(name),
      }),
    })

    const result = await response.json()

    if (!response.ok) {
      console.error("Resend API error:", result)
      return new Response(
        JSON.stringify({ error: "Failed to send email", details: result }),
        { status: response.status, headers: { "Content-Type": "application/json" } }
      )
    }

    console.log(`Welcome email sent successfully to ${email}`, result)

    return new Response(
      JSON.stringify({ success: true, messageId: result.id }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    )
  } catch (error) {
    console.error("Error sending welcome email:", error)
    return new Response(
      JSON.stringify({ error: "Internal server error", message: error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    )
  }
})
