import { Upload, Cog, Map } from "lucide-react"

const steps = [
  {
    number: 1,
    icon: Upload,
    title: "Upload",
    description: "Upload your geospatial file in any common format.",
  },
  {
    number: 2,
    icon: Cog,
    title: "Process",
    description: "Run automated geoprocessing on your data.",
  },
  {
    number: 3,
    icon: Map,
    title: "View",
    description: "Visualize the output on an interactive map.",
  },
]

export function HowItWorks() {
  return (
    <section className="mx-auto mt-16 max-w-3xl md:mt-24">
      <h2 className="mb-12 text-center text-xl font-semibold text-foreground">How It Works</h2>

      <div className="grid gap-8 md:grid-cols-3">
        {steps.map((step, index) => (
          <div key={step.number} className="relative flex flex-col items-center text-center">
            {index < steps.length - 1 && (
              <div className="absolute left-1/2 top-6 hidden h-0.5 w-full bg-gradient-to-r from-primary/50 to-primary/20 md:block" />
            )}

            <div className="relative z-10 mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-lg font-bold text-primary-foreground shadow-lg shadow-primary/25">
              {step.number}
            </div>

            <h3 className="mb-2 font-semibold text-foreground">{step.title}</h3>
            <p className="text-sm text-muted-foreground text-pretty">{step.description}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
