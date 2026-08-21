"use client";

import React from "react";

/**
 * Minimal inline markdown: **bold** and line breaks. Enough for the
 * assistant's chat copy without pulling a full markdown dependency.
 */
export default function MarkdownLite({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, i) => (
        <React.Fragment key={i}>
          {renderBold(line)}
          {i < lines.length - 1 && <br />}
        </React.Fragment>
      ))}
    </>
  );
}

function renderBold(line: string): React.ReactNode[] {
  const parts = line.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}
