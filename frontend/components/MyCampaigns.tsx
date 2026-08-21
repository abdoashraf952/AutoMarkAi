"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { listMyCampaigns, getMyCampaign } from "@/lib/api";
import type { CampaignRecord, CampaignBundle } from "@/lib/api";
import type { AuthUser } from "@/hooks/useAuth";
import { BuildingIcon } from "@/components/Landing";

// ── helpers ────────────────────────────────────────────────────────────────────
function fmt(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
function cap(s?: string | null) {
  if (!s) return "—";
  return s.charAt(0).toUpperCase() + s.slice(1);
}
function budget(b: number | null | undefined) {
  if (b == null) return "—";
  return `$${b.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} USD`;
}

// ── Campaign card ──────────────────────────────────────────────────────────────
function CampaignCard({ c, onClick }: { c: CampaignRecord; onClick: () => void }) {
  const published = c.status === "published";
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4, scale: 1.01 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="group relative w-full cursor-pointer overflow-hidden rounded-3xl p-6 text-left shadow-card transition-all"
      style={{
        background: "linear-gradient(160deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%)",
        border: "1px solid rgba(255,255,255,0.09)",
        backdropFilter: "blur(20px)",
      }}
    >
      {/* gold hover ring */}
      <div
        className="pointer-events-none absolute inset-0 rounded-3xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ border: "1px solid rgba(201,168,76,0.45)", boxShadow: "inset 0 0 24px rgba(201,168,76,0.06)" }}
      />

      {/* top row */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl"
          style={{ background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 45%, #E8C97A 100%)" }}
        >
          <BuildingIcon size={22} />
        </div>
        <span
          className="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest"
          style={
            published
              ? { background: "rgba(201,168,76,0.18)", color: "#E8C97A" }
              : { background: "rgba(255,255,255,0.07)", color: "rgba(255,255,255,0.4)" }
          }
        >
          {published ? "● Published" : "○ Draft"}
        </span>
      </div>

      {/* compound name */}
      <h3 className="mb-1 font-serif text-lg font-bold leading-tight text-white">
        {c.compound_name || "Unnamed Campaign"}
      </h3>

      {/* divider */}
      <div className="mb-4 h-px" style={{ background: "rgba(201,168,76,0.14)" }} />

      {/* meta row */}
      <div className="mb-4 flex flex-wrap gap-3">
        <Pill icon="💰" label={budget(c.budget)} />
        <Pill icon="🌐" label={c.language === "ar" ? "Arabic" : c.language ? "English" : "—"} />
        <Pill icon="📅" label={fmt(c.created_at)} />
      </div>

      {/* Meta campaign ID */}
      {c.meta_campaign_id && (
        <div
          className="rounded-xl px-3 py-2 text-[10px] font-mono"
          style={{ background: "rgba(201,168,76,0.07)", color: "rgba(232,201,122,0.7)" }}
        >
          Campaign {c.meta_campaign_id}
        </div>
      )}

      {/* CTA */}
      <div
        className="mt-4 text-right text-xs font-semibold transition-colors group-hover:text-white"
        style={{ color: "rgba(201,168,76,0.7)" }}
      >
        View details →
      </div>
    </motion.button>
  );
}

function Pill({ icon, label }: { icon: string; label: string }) {
  return (
    <span className="chip gap-1 text-[11px]">
      {icon} {label}
    </span>
  );
}

// ── Detail popup ───────────────────────────────────────────────────────────────
function DetailPopup({ campaign, onClose }: { campaign: CampaignRecord; onClose: () => void }) {
  const b = campaign.campaign_bundle as CampaignBundle | null;
  const published = campaign.status === "published";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-4 py-12"
      style={{ background: "rgba(10,8,5,0.85)", backdropFilter: "blur(14px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 24 }}
        animate={{ opacity: 1, scale: 1,    y: 0  }}
        exit={{   opacity: 0, scale: 0.94,  y: 24 }}
        transition={{ type: "spring", stiffness: 280, damping: 26 }}
        className="relative w-full max-w-2xl rounded-3xl shadow-card"
        style={{
          background: "linear-gradient(180deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.04) 100%)",
          border: "1px solid rgba(201,168,76,0.22)",
          backdropFilter: "blur(24px)",
        }}
      >
        {/* close */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 z-10 flex h-9 w-9 items-center justify-center rounded-full text-white/40 transition hover:text-white"
          style={{ background: "rgba(255,255,255,0.07)" }}
        >
          ✕
        </button>

        {/* header */}
        <div className="rounded-t-3xl px-7 py-6" style={{ borderBottom: "1px solid rgba(201,168,76,0.14)" }}>
          <div className="flex items-center gap-4">
            <div
              className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl shadow-glow"
              style={{ background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 40%, #E8C97A 70%, #D97706 100%)" }}
            >
              <BuildingIcon size={26} />
            </div>
            <div>
              <h2 className="font-serif text-2xl font-bold text-white">
                {campaign.compound_name || "Unnamed Campaign"}
              </h2>
              <div className="mt-1 flex items-center gap-2">
                <span
                  className="rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest"
                  style={
                    published
                      ? { background: "rgba(201,168,76,0.2)", color: "#E8C97A" }
                      : { background: "rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.4)" }
                  }
                >
                  {published ? "● Published" : "○ Draft"}
                </span>
                <span className="text-xs text-white/35">{fmt(campaign.created_at)}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-5 px-7 py-6">
          {/* Quick metrics */}
          <Section title="Overview">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <MetricBox label="Daily Budget" value={budget(b?.media?.daily_budget_usd ?? campaign.budget)} />
              <MetricBox label="Language" value={campaign.language === "ar" ? "Arabic" : "English"} />
              <MetricBox label="Created"  value={fmt(campaign.created_at)} />
              <MetricBox label="Published" value={fmt(campaign.published_at)} />
            </div>
          </Section>

          {/* Meta IDs */}
          {(campaign.meta_campaign_id || campaign.meta_adset_id || campaign.meta_ad_id || campaign.meta_post_id) && (
            <Section title="Meta Ad IDs">
              <div className="space-y-2 rounded-2xl p-4" style={{ background: "rgba(201,168,76,0.05)", border: "1px solid rgba(201,168,76,0.12)" }}>
                <IdRow label="Campaign"  value={campaign.meta_campaign_id} />
                <IdRow label="Ad Set"    value={campaign.meta_adset_id} />
                <IdRow label="Creative"  value={campaign.meta_creative_id} />
                <IdRow label="Ad"        value={campaign.meta_ad_id} />
                <IdRow label="Page Post" value={campaign.meta_post_id} />
              </div>
            </Section>
          )}

          {/* Campaign bundle details */}
          {b && (
            <>
              {/* Product + Campaign */}
              {(b.campaign || b.real_estate_project) && (
                <Section title="Campaign Details">
                  <div className="grid grid-cols-2 gap-2">
                    <InfoRow label="Platform"  value={cap(b.campaign?.platform)} />
                    <InfoRow label="Objective" value={cap(b.campaign?.objective)} />
                    <InfoRow label="Tone"      value={cap(b.campaign?.tone)} />
                    <InfoRow label="Duration"  value={b.real_estate_project?.campaign_duration_days ? `${b.real_estate_project.campaign_duration_days} days` : undefined} />
                    <InfoRow label="Location"  value={b.real_estate_project?.location} />
                    <InfoRow label="Price"     value={b.real_estate_project?.starting_price} />
                    <InfoRow label="Lead via"  value={cap(b.real_estate_project?.lead_destination)} />
                    <InfoRow label="Offer"     value={b.real_estate_project?.offer} />
                  </div>
                </Section>
              )}

              {/* Audience */}
              {b.media?.audience && (
                <Section title="Audience Targeting">
                  <div className="grid grid-cols-2 gap-2">
                    <InfoRow label="Age range"  value={`${b.media.audience.age_min ?? "—"} – ${b.media.audience.age_max ?? "—"}`} />
                    <InfoRow label="Daily budget" value={b.media.daily_budget_usd ? `$${b.media.daily_budget_usd.toFixed(0)} / day` : undefined} />
                    <InfoRow label="Bid strategy" value={cap(b.media.bid_strategy)} />
                    <InfoRow label="Opt. goal"   value={cap(b.media.optimization_goal)} />
                  </div>
                  {(b.media.audience.locations ?? []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(b.media.audience.locations ?? []).map((l) => (
                        <span key={l} className="chip text-[11px]">📍 {l}</span>
                      ))}
                    </div>
                  )}
                  {(b.media.audience.interests ?? []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(b.media.audience.interests ?? []).map((i) => (
                        <span key={i} className="chip text-[11px]">🎯 {i}</span>
                      ))}
                    </div>
                  )}
                </Section>
              )}

              {/* Creative */}
              {b.creative && (b.creative.copies?.length || b.creative.headlines?.length) && (
                <Section title="Ad Creative">
                  {b.creative.headlines?.[0] && (
                    <div className="mb-3 rounded-xl px-4 py-3" style={{ background: "rgba(201,168,76,0.08)" }}>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-white/45">Headline</p>
                      <p className="mt-1 text-sm font-semibold text-white">{b.creative.headlines[0]}</p>
                    </div>
                  )}
                  {b.creative.copies?.[0] && (
                    <div className="rounded-xl px-4 py-3" style={{ background: "rgba(255,255,255,0.04)" }}>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-white/45">Body copy</p>
                      <p className="mt-1 text-sm leading-relaxed text-white/80">{b.creative.copies[0]}</p>
                    </div>
                  )}
                  {b.creative.cta && (
                    <div className="mt-2 text-xs text-white/40">CTA: <span className="text-white/70">{b.creative.cta}</span></div>
                  )}
                </Section>
              )}

              {/* Strategy */}
              {b.strategy?.target_persona && (
                <Section title="Marketing Strategy">
                  <div className="grid grid-cols-2 gap-2">
                    <InfoRow label="Segment"   value={b.strategy.target_persona.primary_segment} />
                    <InfoRow label="Archetype" value={b.strategy.target_persona.archetype} />
                  </div>
                  {(b.strategy.messaging_angles ?? []).length > 0 && (
                    <div className="mt-3">
                      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-white/45">Messaging angles</p>
                      <div className="flex flex-wrap gap-1.5">
                        {(b.strategy.messaging_angles ?? []).map((a, i) => (
                          <span key={i} className="chip text-[11px]">{a}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </Section>
              )}
            </>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <span className="text-[11px] font-bold uppercase tracking-[0.18em]" style={{ color: "#C9A84C" }}>
          {title}
        </span>
        <span className="h-px flex-1" style={{ background: "rgba(201,168,76,0.18)" }} />
      </div>
      {children}
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl p-3" style={{ background: "rgba(255,255,255,0.05)" }}>
      <p className="text-[10px] uppercase tracking-wider text-white/40">{label}</p>
      <p className="mt-0.5 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  if (!value || value === "—") return null;
  return (
    <div className="flex flex-col gap-0.5 rounded-xl px-3 py-2" style={{ background: "rgba(255,255,255,0.04)" }}>
      <span className="text-[9px] uppercase tracking-wider text-white/35">{label}</span>
      <span className="text-xs text-white/80">{value}</span>
    </div>
  );
}

function IdRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between gap-3 text-xs">
      <span className="text-white/40">{label}</span>
      <span className="font-mono text-[11px]" style={{ color: "rgba(232,201,122,0.8)" }}>{value}</span>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function MyCampaigns({
  user,
  onBack,
}: {
  user:    AuthUser;
  onBack:  () => void;
}) {
  const [campaigns,  setCampaigns]  = useState<CampaignRecord[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState("");
  const [selected,   setSelected]   = useState<CampaignRecord | null>(null);
  const [loadingId,  setLoadingId]  = useState<string | null>(null);

  useEffect(() => {
    listMyCampaigns()
      .then(setCampaigns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const openDetail = async (id: string) => {
    setLoadingId(id);
    try {
      const full = await getMyCampaign(id);
      setSelected(full);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load campaign");
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <main className="flex h-[100dvh] flex-col overflow-hidden">
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-5"
        style={{ borderBottom: "1px solid rgba(201,168,76,0.12)" }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex h-9 w-9 items-center justify-center rounded-2xl text-white/50 transition hover:text-white"
            style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
          >
            ←
          </button>
          <div>
            <h1 className="font-serif text-xl font-bold accent-gradient-text">My Campaigns</h1>
            <p className="text-[11px] text-white/35">{user.email}</p>
          </div>
        </div>
        <span className="chip">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: "linear-gradient(135deg, #C9A84C, #E8C97A)" }}
          />
          {campaigns.length} campaign{campaigns.length !== 1 ? "s" : ""}
        </span>
      </header>

      {/* Body */}
      <div className="flex-1 overflow-y-auto scroll-area px-6 py-6">
        {loading && (
          <div className="flex h-64 items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div
                className="h-10 w-10 animate-spin rounded-full"
                style={{ border: "2px solid rgba(201,168,76,0.2)", borderTopColor: "#C9A84C" }}
              />
              <p className="text-sm text-white/40">Loading campaigns…</p>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-2xl px-5 py-4 text-sm text-red-300" style={{ background: "rgba(239,68,68,0.1)" }}>
            {error}
          </div>
        )}

        {!loading && !error && campaigns.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex h-64 flex-col items-center justify-center gap-4 text-center"
          >
            <div
              className="flex h-20 w-20 items-center justify-center rounded-3xl"
              style={{ background: "rgba(201,168,76,0.08)", border: "1px solid rgba(201,168,76,0.18)" }}
            >
              <BuildingIcon size={36} />
            </div>
            <div>
              <p className="font-serif text-lg font-semibold text-white">No campaigns yet</p>
              <p className="mt-1 text-sm text-white/40">
                Create your first real estate ad campaign to see it here.
              </p>
            </div>
            <button onClick={onBack} className="btn-primary px-6 py-3 text-sm">
              Create a campaign →
            </button>
          </motion.div>
        )}

        {!loading && campaigns.length > 0 && (
          <div className="mx-auto grid max-w-5xl grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {campaigns.map((c, i) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
              >
                <CampaignCard
                  c={c}
                  onClick={() => openDetail(c.id)}
                />
                {loadingId === c.id && (
                  <div className="mt-2 flex justify-center">
                    <div
                      className="h-4 w-4 animate-spin rounded-full"
                      style={{ border: "2px solid rgba(201,168,76,0.2)", borderTopColor: "#C9A84C" }}
                    />
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Detail popup */}
      <AnimatePresence>
        {selected && (
          <DetailPopup campaign={selected} onClose={() => setSelected(null)} />
        )}
      </AnimatePresence>
    </main>
  );
}
