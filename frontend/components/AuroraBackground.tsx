"use client";

/**
 * Animated ambient backdrop — warm gold aurora blobs behind a subtle
 * architectural grid, with a city skyline silhouette along the bottom.
 * Pure CSS animation (defined in tailwind.config.ts), GPU-friendly,
 * sits fixed behind all content.
 */
export default function AuroraBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" style={{ background: "#0A0805" }}>
      {/* Warm radial vignette — golden warmth from the top */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(130% 120% at 50% 0%, #1A1205 0%, #0E0B06 45%, #0A0805 70%)",
        }}
      />

      {/* Primary gold blob — top-left */}
      <div
        className="absolute -left-40 -top-40 h-[55vh] w-[55vh] animate-aurora-1 rounded-full blur-[120px]"
        style={{ background: "rgba(201,168,76,0.28)" }}
      />

      {/* Secondary amber blob — top-right */}
      <div
        className="absolute right-[-15%] top-[10%] h-[50vh] w-[50vh] animate-aurora-2 rounded-full blur-[120px]"
        style={{ background: "rgba(217,119,6,0.18)" }}
      />

      {/* Copper/terra blob — bottom-left */}
      <div
        className="absolute bottom-[-20%] left-[20%] h-[45vh] w-[45vh] animate-aurora-1 rounded-full blur-[130px]"
        style={{ background: "rgba(146,64,14,0.14)" }}
      />

      {/* Subtle center warmth */}
      <div
        className="absolute left-1/2 top-1/3 h-[40vh] w-[60vw] -translate-x-1/2 rounded-full blur-[160px]"
        style={{ background: "rgba(201,168,76,0.055)" }}
      />

      {/* Architectural blueprint grid — golden tint */}
      <div
        className="absolute inset-0 opacity-[0.032]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(232,201,122,0.9) 1px, transparent 1px), linear-gradient(90deg, rgba(232,201,122,0.9) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage:
            "radial-gradient(100% 100% at 50% 0%, black, transparent 78%)",
        }}
      />

      {/* City skyline silhouette */}
      <div className="absolute bottom-0 left-0 right-0 opacity-[0.06]">
        <svg
          viewBox="0 0 1440 200"
          preserveAspectRatio="none"
          className="w-full"
          style={{ display: "block" }}
        >
          {/* Main skyline filled shape */}
          <path
            d="
              M0,200 L0,165 L40,165 L40,148 L55,148 L55,128 L68,128 L68,108
              L78,108 L78,88 L88,88 L88,72 L98,72 L98,88 L108,88 L108,108
              L120,108 L120,128 L135,128 L135,148 L155,148 L155,125 L168,125
              L168,102 L180,102 L180,80 L192,80 L192,62 L202,62 L202,80
              L214,80 L214,102 L226,102 L226,125 L245,125 L245,108 L258,108
              L258,85 L270,85 L270,62 L282,62 L282,42 L295,42 L295,62 L308,62
              L308,85 L320,85 L320,108 L338,108 L338,88 L350,88 L350,65 L362,65
              L362,45 L375,45 L375,28 L388,28 L388,45 L400,45 L400,65 L412,65
              L412,88 L428,88 L428,68 L440,68 L440,45 L452,45 L452,25 L465,25
              L465,10 L478,10 L478,25 L490,25 L490,45 L502,45 L502,68 L518,68
              L518,50 L530,50 L530,30 L542,30 L542,12 L554,12 L554,2 L565,2
              L565,0 L574,0 L574,2 L584,2 L584,12 L596,12 L596,30 L608,30
              L608,50 L622,50 L622,32 L634,32 L634,15 L645,15 L645,5 L655,5
              L655,15 L666,15 L666,32 L678,32 L678,50 L694,50 L694,32 L706,32
              L706,15 L717,15 L717,5 L727,5 L727,15 L738,15 L738,32 L750,32
              L750,50 L765,50 L765,32 L778,32 L778,15 L789,15 L789,5 L800,5
              L800,15 L811,15 L811,32 L822,32 L822,50 L838,50 L838,32 L850,32
              L850,18 L862,18 L862,8 L872,8 L872,18 L884,18 L884,32 L896,32
              L896,50 L912,50 L912,68 L925,68 L925,50 L936,50 L936,35 L948,35
              L948,50 L960,50 L960,68 L975,68 L975,88 L988,88 L988,70 L1000,70
              L1000,55 L1012,55 L1012,70 L1025,70 L1025,88 L1040,88 L1040,108
              L1055,108 L1055,88 L1068,88 L1068,70 L1082,70 L1082,88 L1096,88
              L1096,108 L1112,108 L1112,128 L1126,128 L1126,108 L1140,108
              L1140,88 L1153,88 L1153,108 L1167,108 L1167,128 L1185,128
              L1185,145 L1205,145 L1205,128 L1218,128 L1218,112 L1230,112
              L1230,128 L1244,128 L1244,145 L1265,145 L1265,160 L1295,160
              L1295,145 L1315,145 L1315,160 L1345,160 L1345,172 L1385,172
              L1385,158 L1415,158 L1415,172 L1440,172 L1440,200 Z
            "
            fill="rgba(232,201,122,0.85)"
          />

          {/* Antenna spires on the tallest buildings */}
          <rect x="566" y="-8" width="2.5" height="10" rx="1" fill="rgba(232,201,122,0.6)" />
          <rect x="465" y="0"  width="2"   height="12" rx="1" fill="rgba(232,201,122,0.5)" />
          <rect x="862" y="-2" width="2"   height="11" rx="1" fill="rgba(232,201,122,0.5)" />
          <rect x="375" y="18" width="2"   height="12" rx="1" fill="rgba(232,201,122,0.45)" />

          {/* Ground strip */}
          <rect x="0" y="193" width="1440" height="7" fill="rgba(201,168,76,0.3)" />
        </svg>
      </div>

      {/* Subtle warm glow at horizon (where skyline meets sky) */}
      <div
        className="absolute bottom-0 left-0 right-0 h-24"
        style={{
          background:
            "linear-gradient(to top, rgba(201,168,76,0.06) 0%, transparent 100%)",
        }}
      />
    </div>
  );
}
