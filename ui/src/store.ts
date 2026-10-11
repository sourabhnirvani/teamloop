// Everything live in the app: bots, chats, each chat's items, who is working, unread counts and the mascots'
// moves. Server events update it; after a (re)connect or a gap in events it reloads from the server, so
// nothing said while the app was away goes missing and no bot stays stuck "working".

import { useCallback, useEffect, useRef, useState } from "react";
import { api, listen, type ApprovalEvent, type Bot, type Chat, type Message, type ServerEvent } from "./api";
import type { Move } from "./Avatar";
import type { Handoff } from "./CrewRoom";

export type Item =
  | { kind: "msg"; key: string; ts: number; sender: string; text: string; mkind: string }
  | { kind: "step"; key: string; ts: number; bot: string; tool: string; status: "start" | "done" | "fail"; text?: string }
  | { kind: "approval"; key: string; ts: number; id: string; bot: string; title: string; details: string; screenshot?: string | null; status?: string }
  | { kind: "shot"; key: string; ts: number; bot: string; url: string };

const now = () => Date.now() / 1000;
let seq = 0;
const uid = (p: string) => `${p}${++seq}`;

const msgItem = (m: Message): Item => ({ kind: "msg", key: `m${m.id}`, ts: m.ts, sender: m.sender, text: m.text, mkind: m.kind });
const cardItem = (e: ApprovalEvent): Item => ({ kind: "approval", key: `a${e.id}`, ts: now(), id: e.id, bot: e.bot, title: e.title, details: e.details, screenshot: e.screenshot });
const byTime = (a: Item, b: Item) => a.ts - b.ts;
const FAILED = /^failed\b/i;

export function isFailure(text: string) {
  return FAILED.test(text.trim());
}

export function useCrew(active: string | null) {
  const [bots, setBots] = useState<Record<string, Bot>>({});
  const [chats, setChats] = useState<Chat[]>([]);
  const [items, setItems] = useState<Record<string, Item[]>>({});
  const [typing, setTyping] = useState<Record<string, string[]>>({});
  const [unread, setUnread] = useState<Record<string, number>>({});
  const [moves, setMoves] = useState<Record<string, Move>>({});
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const [tools, setTools] = useState<Record<string, string>>({}); // bot -> the tool it's using right now
  const [asleep, setAsleep] = useState(false);
  const [live, setLive] = useState(false);
  const [ready, setReady] = useState(false);
  const activeRef = useRef(active);
  const botsRef = useRef(bots);
  const timers = useRef<Record<string, number>>({});
  activeRef.current = active;
  botsRef.current = bots;

  useEffect(() => () => Object.values(timers.current).forEach((t) => window.clearTimeout(t)), []);

  const move = useCallback((bot: string, m: Move, ms = 1500) => {
    setMoves((all) => ({ ...all, [bot]: m }));
    window.clearTimeout(timers.current[bot]);
    if (m !== "think" && m !== "ask" && m !== "idle") {
      timers.current[bot] = window.setTimeout(() => setMoves((all) => ({ ...all, [bot]: "idle" })), ms);
    }
  }, []);

  const loadBots = useCallback(() => api.bots().then((b) => setBots(Object.fromEntries(b.map((x) => [x.id, x])))), []);
  const loadChats = useCallback(() => api.chats().then(setChats), []);

  const loadMessages = useCallback(async (chatId: string) => {
    const ms = await api.messages(chatId);
    setItems((all) => {
      const extra = (all[chatId] ?? []).filter((i) => i.kind !== "msg");
      return { ...all, [chatId]: [...ms.map(msgItem), ...extra].sort(byTime) };
    });
  }, []);

  // after a (re)connect: chats, the open chat, who is working, and cards still waiting
  const resync = useCallback(async () => {
    try {
      const [state] = await Promise.all([api.state(), loadBots(), loadChats()]);
      setTyping(state.typing);
      setAsleep(state.asleep);
      setTools({});
      setMoves((all) => {
        const next: Record<string, Move> = {};
        for (const [id, m] of Object.entries(all)) next[id] = m === "think" || m === "ask" ? "idle" : m;
        for (const ids of Object.values(state.typing)) for (const id of ids) next[id] = "think";
        for (const card of state.approvals) next[card.bot] = "ask";
        return next;
      });
      setItems((all) => {
        const out = { ...all };
        const waiting = new Set(state.approvals.map((c) => c.id));
        for (const [chat, list] of Object.entries(out)) {
          // cards that were answered while we were away aren't waiting any more
          out[chat] = list.map((i) => (i.kind === "approval" && !i.status && !waiting.has(i.id) ? { ...i, status: "answered" } : i));
        }
        for (const card of state.approvals) {
          const list = out[card.chat_id] ?? [];
          if (!list.some((i) => i.kind === "approval" && i.id === card.id)) out[card.chat_id] = [...list, cardItem(card)].sort(byTime);
        }
        return out;
      });
      if (activeRef.current) await loadMessages(activeRef.current);
      setReady(true);
    } catch {
      /* the server isn't up yet: the stream reconnects and calls this again */
    }
  }, [loadBots, loadChats, loadMessages]);

  useEffect(() => {
    if (!active) return;
    loadMessages(active).catch(() => {});
    setUnread((u) => (u[active] ? { ...u, [active]: 0 } : u));
  }, [active, loadMessages]);

  useEffect(() => {
    const add = (chat: string, item: Item) => setItems((all) => ({ ...all, [chat]: [...(all[chat] ?? []), item] }));
    const bump = (chat: string) => {
      if (chat !== activeRef.current) setUnread((u) => ({ ...u, [chat]: (u[chat] ?? 0) + 1 }));
    };
    const onEvent = (e: ServerEvent) => {
      if (e.type === "usage") return;
      if (e.type === "settings") {
        loadBots().catch(() => {});
        return;
      }
      const chat = e.chat_id;
      switch (e.type) {
        case "message": {
          setItems((all) => {
            const list = all[chat] ?? [];
            if (list.some((i) => i.key === `m${e.message.id}`)) return all;
            return { ...all, [chat]: [...list, msgItem(e.message)] };
          });
          setChats((cs) => cs.map((c) => (c.id === chat ? { ...c, last: { sender: e.message.sender, text: e.message.text, kind: e.message.kind, ts: e.message.ts } } : c)));
          const m = e.message;
          // the sleep / wake replies (crew/commands.py) switch the 💤 sign
          if (m.sender !== "user" && /^(Going to sleep|The crew is asleep)/.test(m.text)) setAsleep(true);
          if (m.sender !== "user" && /^(Awake and ready|Already awake)/.test(m.text)) setAsleep(false);
          if (m.sender !== "user") {
            if (m.kind === "handoff") {
              const name = m.text.match(/^@(\w+)/)?.[1]?.toLowerCase();
              const to = Object.values(botsRef.current).find((b) => b.id === name || b.name.toLowerCase() === name);
              if (to) setHandoff({ from: m.sender, to: to.id, key: Date.now() });
              move(m.sender, "talk");
            } else if (m.kind === "stopped") {
              move(m.sender, "idle");
            } else {
              move(m.sender, isFailure(m.text) ? "oops" : /^not mine:/i.test(m.text) ? "talk" : "cheer");
            }
            bump(chat);
          }
          break;
        }
        case "typing":
          setTyping((t) => {
            const set = new Set(t[chat] ?? []);
            if (e.on) set.add(e.bot);
            else set.delete(e.bot);
            return { ...t, [chat]: [...set] };
          });
          if (e.on) move(e.bot, "think");
          else {
            setMoves((all) => (all[e.bot] === "think" ? { ...all, [e.bot]: "idle" } : all)); // never stuck thinking
            setTools((t) => (e.bot in t ? Object.fromEntries(Object.entries(t).filter(([k]) => k !== e.bot)) : t));
          }
          break;
        case "step":
          if (e.status === "start") {
            add(chat, { kind: "step", key: uid("s"), ts: now(), bot: e.bot, tool: e.tool, status: "start" });
            setTools((t) => ({ ...t, [e.bot]: e.tool }));
          } else {
            setTools((t) => (t[e.bot] === e.tool ? Object.fromEntries(Object.entries(t).filter(([k]) => k !== e.bot)) : t));
            setItems((all) => {
              const list = [...(all[chat] ?? [])];
              for (let i = list.length - 1; i >= 0; i--) {
                const it = list[i];
                if (it.kind === "step" && it.status === "start" && it.bot === e.bot && it.tool === e.tool) {
                  list[i] = { ...it, status: e.status, text: e.text };
                  break;
                }
              }
              return { ...all, [chat]: list };
            });
            if (e.status === "fail") move(e.bot, "oops");
          }
          break;
        case "approval":
          setItems((all) => {
            const list = all[chat] ?? [];
            if (list.some((i) => i.kind === "approval" && i.id === e.id)) return all;
            return { ...all, [chat]: [...list, cardItem(e)] };
          });
          move(e.bot, "ask");
          bump(chat);
          break;
        case "approval_done": {
          let bot = "";
          setItems((all) => ({
            ...all,
            [chat]: (all[chat] ?? []).map((i) => {
              if (i.kind === "approval" && i.id === e.id) {
                bot = i.bot;
                return { ...i, status: e.status };
              }
              return i;
            }),
          }));
          setMoves((all) => {
            const who = bot || Object.keys(all).find((k) => all[k] === "ask");
            return who && all[who] === "ask" ? { ...all, [who]: "think" } : all;
          });
          break;
        }
        case "screenshot":
          add(chat, { kind: "shot", key: uid("p"), ts: now(), bot: e.bot, url: e.url });
          break;
      }
    };
    return listen({ onEvent, onLive: setLive, onResync: () => void resync() });
  }, [move, resync, loadBots]);

  const markAnswered = useCallback((chatId: string, approvalId: string, status: string) => {
    setItems((all) => ({
      ...all,
      [chatId]: (all[chatId] ?? []).map((i) => (i.kind === "approval" && i.id === approvalId && !i.status ? { ...i, status } : i)),
    }));
  }, []);

  return { bots, chats, items, typing, unread, moves, handoff, tools, asleep, live, ready, loadChats, loadBots, markAnswered };
}
