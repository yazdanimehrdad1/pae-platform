import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// The AI's answer as Markdown (GitHub flavour: tables, lists, bold). react-markdown never renders
// raw HTML from the answer, so a model-written <script> or <img> stays plain text.

const components: Components = {
  p: ({ children }) => <p className="my-1.5 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-1.5 list-disc space-y-0.5 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 list-decimal space-y-0.5 pl-5">{children}</ol>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  h1: ({ children }) => <p className="my-1.5 font-semibold">{children}</p>,
  h2: ({ children }) => <p className="my-1.5 font-semibold">{children}</p>,
  h3: ({ children }) => <p className="my-1.5 font-semibold">{children}</p>,
  code: ({ children }) => <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{children}</code>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer noopener" className="underline underline-offset-2">{children}</a>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children, style }) => <th style={style} className="border-b px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children, style }) => <td style={style} className="border-b border-border/50 px-2 py-1 tabular-nums">{children}</td>,
};

export function AnswerMarkdown({ text }: { text: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{text}</ReactMarkdown>;
}
