"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { CampaignBundle } from "@/lib/types";

/** Live, switchable Facebook / Instagram ad mockups built from the bundle. */
export default function AdPreview({
  bundle,
  image,
}: {
  bundle: CampaignBundle;
  image: string;
}) {
  const [tab, setTab] = useState<"facebook" | "instagram">("facebook");

  const creative = bundle.creative || {};
  const product = bundle.product || {};
  const pageName = `AutoMark — ${product.type || "Brand"}`;
  const copy = creative.copies?.[0] || "";
  const headline = creative.headlines?.[0] || "";
  const cta = creative.cta || "Learn More";
  const initial = (pageName[0] || "A").toUpperCase();

  return (
    <div className="w-full">
      <div className="mb-3 flex gap-2">
        {(["facebook", "instagram"] as const).map((p) => (
          <button
            key={p}
            onClick={() => setTab(p)}
            className={`rounded-xl px-3 py-1.5 text-xs font-semibold capitalize transition-all ${
              tab === p
                ? "bg-white/15 text-white"
                : "bg-white/5 text-white/50 hover:text-white/80"
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      <motion.div
        key={tab}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto max-w-[360px]"
      >
        {tab === "facebook" ? (
          <div className="overflow-hidden rounded-2xl bg-white text-[#050505] shadow-card">
            <div className="flex items-center gap-2.5 p-3">
              <Avatar initial={initial} />
              <div className="leading-tight">
                <div className="text-[13px] font-semibold">{pageName}</div>
                <div className="text-[11px] text-[#65676b]">
                  Sponsored · <span className="text-[#1877f2]">●</span>
                </div>
              </div>
            </div>
            <div className="px-3 pb-2 text-[13px] leading-snug">{copy.slice(0, 200)}</div>
            <AdImage src={image} />
            <div className="flex items-center justify-between bg-[#f0f2f5] px-3 py-2.5">
              <div className="text-[13px] font-semibold">{headline.slice(0, 40)}</div>
              <div className="rounded-md border border-[#ccd0d5] bg-[#e7e9eb] px-3 py-1.5 text-[12px] font-semibold">
                {cta}
              </div>
            </div>
          </div>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-[#dbdbdb] bg-white text-[#262626] shadow-card">
            <div className="flex items-center gap-2.5 p-2.5">
              <Avatar initial={initial} instagram />
              <div className="text-[12px] font-semibold">{pageName}</div>
            </div>
            <AdImage src={image} square />
            <div className="p-3">
              <div className="mb-1 text-[12px]">
                <b>{pageName}</b> {copy.slice(0, 140)}
              </div>
              <div className="mb-2 text-[11px] text-[#8e8e8e]">{headline}</div>
              <div className="rounded-md bg-[#e0e0e0] py-2 text-center text-[12px] font-semibold">
                {cta}
              </div>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}

function Avatar({ initial, instagram }: { initial: string; instagram?: boolean }) {
  return (
    <div
      className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
      style={{
        background: instagram
          ? "linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888)"
          : "#1877f2",
      }}
    >
      {initial}
    </div>
  );
}

function AdImage({ src, square }: { src: string; square?: boolean }) {
  if (!src) {
    return (
      <div
        className={`flex w-full items-center justify-center bg-[#e4e6ea] text-[13px] text-[#65676b] ${
          square ? "aspect-square" : "h-44"
        }`}
      >
        No image available
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt="Ad creative"
      className={`w-full object-cover ${square ? "aspect-square" : "max-h-72"}`}
    />
  );
}
