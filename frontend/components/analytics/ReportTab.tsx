"use client";

import React, { useMemo } from "react";
import { Card, EmptyState, SectionTitle } from "./ui";

/**
 * Small block-level markdown renderer for the executive report: headings,
 * bullet/numbered lists, bold, and paragraphs. The project deliberately avoids
 * a markdown dependency (see MarkdownLite), so this covers the subset the
 * report generator actually emits.
 */
function renderInline(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          className="rounded px-1.5 py-0.5 text-[0.9em] text-white/80"
          style={{ background: "rgba(0,0,0,0.35)" }}
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

function ReportMarkdown({ text }: { text: string }) {
  const blocks = useMemo(() => {
    const out: React.ReactNode[] = [];
    const lines = text.split("\n");
    let list: string[] = [];
    let ordered = false;

    const flushList = (key: string | number) => {
      if (!list.length) return;
      const Tag = ordered ? "ol" : "ul";
      out.push(
        <Tag
          key={`l${key}`}
          className={`my-3 space-y-1.5 pl-5 ${ordered ? "list-decimal" : "list-disc"}`}
          style={{ color: "rgba(232,234,245,0.65)" }}
        >
          {list.map((item, i) => (
            <li key={i} className="text-[13.5px] leading-relaxed">
              {renderInline(item)}
            </li>
          ))}
        </Tag>
      );
      list = [];
    };

    lines.forEach((raw, idx) => {
      const line = raw.trimEnd();

      const heading = /^(#{1,4})\s+(.*)$/.exec(line);
      if (heading) {
        flushList(idx);
        const level = heading[1].length;
        const size =
          level === 1 ? "text-xl" : level === 2 ? "text-lg" : "text-base";
        out.push(
          <h3
            key={idx}
            className={`mb-2 mt-5 font-serif font-bold text-white ${size}`}
          >
            {renderInline(heading[2])}
          </h3>
        );
        return;
      }

      const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
      if (bullet) {
        if (ordered) flushList(idx);
        ordered = false;
        list.push(bullet[1]);
        return;
      }

      const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
      if (numbered) {
        if (!ordered) flushList(idx);
        ordered = true;
        list.push(numbered[1]);
        return;
      }

      flushList(idx);

      if (!line.trim()) return;

      if (/^[-—_]{3,}$/.test(line.trim())) {
        out.push(
          <hr key={idx} className="my-5" style={{ borderColor: "rgba(255,255,255,0.1)" }} />
        );
        return;
      }

      out.push(
        <p key={idx} className="my-2 text-[13.5px] leading-relaxed text-white/65">
          {renderInline(line)}
        </p>
      );
    });

    flushList("end");
    return out;
  }, [text]);

  return <div>{blocks}</div>;
}

export default function ReportTab({
  report,
  fileName,
  generatedAt,
}: {
  report: string | null;
  fileName: string;
  generatedAt: string | null;
}) {
  if (!report) {
    return <EmptyState>No executive report was generated for this analysis.</EmptyState>;
  }

  const download = () => {
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileName.replace(/\.[^.]+$/, "")}_report.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <SectionTitle
          sub={generatedAt ? `Generated ${new Date(generatedAt).toLocaleString()}` : undefined}
        >
          Executive Report
        </SectionTitle>
        <button
          onClick={download}
          className="flex-shrink-0 rounded-xl px-3.5 py-2 text-[11px] font-bold uppercase tracking-wider transition-transform hover:scale-[1.03]"
          style={{
            background: "linear-gradient(135deg, #B8860B 0%, #C9A84C 45%, #E8C97A 100%)",
            color: "#1a1408",
          }}
        >
          Download .md
        </button>
      </div>
      <div className="max-h-[60vh] overflow-y-auto pr-2">
        <ReportMarkdown text={report} />
      </div>
    </Card>
  );
}
