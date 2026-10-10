import type { ReactNode } from "react";

// Just enough markdown for bot replies: **bold**, `code`, [text](url), bare links and "- " / "1. " lists.
// Builds React elements (never HTML strings), and only http(s) links become clickable.
// URLs take only the characters a URL can hold (ASCII), and never end on punctuation.
const URL_CHARS = "[A-Za-z0-9\\-._~:/?#@!$&*+,;=%']";
const INLINE = new RegExp(
  `(\\*\\*[^*\\n]+\\*\\*|\`[^\`\\n]+\`|\\[[^\\]\\n]+\\]\\(https?://${URL_CHARS}+\\)|https?://${URL_CHARS}*[A-Za-z0-9/#=_\\-])`,
  "g",
);

function inline(text: string, key: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    const k = `${key}-${i}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <b key={k}>{part.slice(2, -2)}</b>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return <code key={k}>{part.slice(1, -1)}</code>;
    const md = /^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/.exec(part);
    if (md) return <a key={k} href={md[2]} target="_blank" rel="noreferrer noopener">{md[1]}</a>;
    if (/^https?:\/\//.test(part)) return <a key={k} href={part} target="_blank" rel="noreferrer noopener">{part}</a>;
    return part;
  });
}

export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const items = list.items.map((t, i) => <li key={i}>{inline(t, `li${blocks.length}-${i}`)}</li>);
    blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
    list = null;
  };
  for (const line of text.split("\n")) {
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const item = bullet ?? numbered;
    if (item) {
      const ordered = !bullet;
      if (!list || list.ordered !== ordered) {
        flush();
        list = { ordered, items: [] };
      }
      list.items.push(item[1]);
      continue;
    }
    flush();
    blocks.push(line.trim() ? <p key={blocks.length}>{inline(line, `p${blocks.length}`)}</p> : null);
  }
  flush();
  return <div className="text">{blocks}</div>;
}
