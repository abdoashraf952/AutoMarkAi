"use client";

/**
 * Animated ambient backdrop — slow-drifting aurora blobs behind a subtle
 * grain/noise layer. Pure CSS animation (defined in tailwind.config.ts),
 * GPU-friendly, sits fixed behind all content.
 */
export default function AuroraBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-ink-950">
      {/* radial vignette base */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 120% at 50% 0%, #131c38 0%, #070b1a 62%)",
        }}
      />

      {/* drifting color blobs */}
      <div className="absolute -left-40 -top-40 h-[55vh] w-[55vh] animate-aurora-1 rounded-full bg-accent-violet/30 blur-[120px]" />
      <div className="absolute right-[-15%] top-[10%] h-[50vh] w-[50vh] animate-aurora-2 rounded-full bg-accent-cyan/20 blur-[120px]" />
      <div className="absolute bottom-[-20%] left-[20%] h-[45vh] w-[45vh] animate-aurora-1 rounded-full bg-accent-pink/15 blur-[130px]" />

      {/* fine grid lines for depth */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage:
            "radial-gradient(100% 100% at 50% 0%, black, transparent 70%)",
        }}
      />
    </div>
  );
}
