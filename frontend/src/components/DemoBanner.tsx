const DEMO_BANNER_TEXT = import.meta.env.VITE_DEMO_BANNER as string | undefined

export function DemoBanner() {
  if (!DEMO_BANNER_TEXT) {
    return null
  }

  return (
    <div className="demo-banner" role="status">
      {DEMO_BANNER_TEXT}
    </div>
  )
}
