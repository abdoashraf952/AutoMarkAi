"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Landing from "@/components/Landing";
import ChatExperience from "@/components/ChatExperience";

export default function Page() {
  const [view, setView] = useState<"home" | "chat">("home");

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={view}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3 }}
      >
        {view === "home" ? (
          <Landing onStart={() => setView("chat")} />
        ) : (
          <ChatExperience onEnd={() => setView("home")} />
        )}
      </motion.div>
    </AnimatePresence>
  );
}
