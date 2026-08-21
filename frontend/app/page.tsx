"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Landing from "@/components/Landing";
import ChatExperience from "@/components/ChatExperience";
import AuthModal from "@/components/AuthModal";
import MyCampaigns from "@/components/MyCampaigns";
import AnalyticsExperience from "@/components/analytics/AnalyticsExperience";
import { useAuth } from "@/hooks/useAuth";

type View = "home" | "chat" | "campaigns" | "analytics";

export default function Page() {
  const auth = useAuth();
  const [view,     setView]     = useState<View>("home");
  const [showAuth, setShowAuth] = useState(false);
  // "intended" view to navigate to after successful auth
  const [afterAuth, setAfterAuth] = useState<View>("chat");

  const requireAuth = (targetView: View) => {
    if (auth.user) {
      setView(targetView);
    } else {
      setAfterAuth(targetView);
      setShowAuth(true);
    }
  };

  const handleAuthSuccess = () => {
    setShowAuth(false);
    setView("home");   // always land on home as a logged-in user
  };

  // Don't render anything until auth state is restored from localStorage
  if (auth.loading) {
    return (
      <div className="flex h-[100dvh] items-center justify-center">
        <div
          className="h-10 w-10 animate-spin rounded-full"
          style={{ border: "2px solid rgba(201,168,76,0.2)", borderTopColor: "#C9A84C" }}
        />
      </div>
    );
  }

  return (
    <>
      <AnimatePresence mode="wait">
        {view === "home" && (
          <motion.div
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <Landing
              onStart={() => requireAuth("chat")}
              user={auth.user}
              onMyCampaigns={() => requireAuth("campaigns")}
              onAnalytics={() => requireAuth("analytics")}
              onLogout={() => { auth.logout(); setView("home"); }}
            />
          </motion.div>
        )}

        {view === "chat" && auth.user && (
          <motion.div
            key="chat"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <ChatExperience onEnd={() => setView("home")} />
          </motion.div>
        )}

        {view === "campaigns" && auth.user && (
          <motion.div
            key="campaigns"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <MyCampaigns user={auth.user} onBack={() => setView("home")} />
          </motion.div>
        )}

        {view === "analytics" && auth.user && (
          <motion.div
            key="analytics"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <AnalyticsExperience user={auth.user} onBack={() => setView("home")} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Auth modal — sits above everything */}
      <AnimatePresence>
        {showAuth && (
          <AuthModal
            auth={auth}
            onSuccess={handleAuthSuccess}
            onClose={() => setShowAuth(false)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
