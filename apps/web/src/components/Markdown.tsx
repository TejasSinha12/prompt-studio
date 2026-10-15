"use client";

import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

/**
 * Safe Markdown rendering for untrusted content:
 * - raw HTML in the source is NOT rendered (no rehype-raw),
 * - output is sanitized with rehype-sanitize (GitHub schema),
 * - URLs are restricted to safe protocols (javascript:, data:, vbscript: dropped),
 * - links open in a new tab without referrer or opener.
 */
const SAFE_PROTOCOL = /^(https?:|mailto:|#|\/)/i;

export function safeUrl(url: string): string {
  const cleaned = defaultUrlTransform(url);
  return SAFE_PROTOCOL.test(cleaned) ? cleaned : "";
}

export function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div className={`prose-ps ${className ?? ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        urlTransform={safeUrl}
        components={{
          a: ({ href, children }) => (
            <a href={href || undefined} target="_blank" rel="noopener noreferrer nofollow">
              {children}
            </a>
          ),
          img: ({ alt }) => <span className="text-muted">[image: {alt || "no description"} — not loaded]</span>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
