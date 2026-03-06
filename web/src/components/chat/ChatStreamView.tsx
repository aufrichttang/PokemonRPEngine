"use client";

import { Fragment, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ActionOptionV2 } from "@/lib/schemas/types";

export type ChatBubble = {
  id: string;
  role: "user" | "assistant";
  text: string;
  turnIndex?: number;
  actionOptions?: ActionOptionV2[];
};

type Props = {
  messages: ChatBubble[];
  onOptionClick?: (opt: ActionOptionV2) => void;
};

const JSON_BLOCK_RE = /<!--JSON-->[\s\S]*?<!--\/JSON-->/gi;
const JSON_FENCE_RE = /```(?:json)?[\s\S]*?```/gi;
const JSON_OBJECT_TAIL_RE = /\{[\s\S]*?"(?:facts_used|state_update|open_threads_update|action_options)"[\s\S]*$/i;
const UNICODE_NOISE_RE = /[锛锛銆鈥€�]/g;
const KEYWORDS = /(神兽|恋爱|主线|任务|道馆|徽章|危机|线索|奖励|目标|抉择|羁绊)/g;

function sanitizeAssistantText(text: string): string {
  return text
    .replace(JSON_BLOCK_RE, "")
    .replace(JSON_FENCE_RE, "")
    .replace(JSON_OBJECT_TAIL_RE, "")
    .replace(UNICODE_NOISE_RE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function smartBreak(text: string): string {
  return text
    .replace(/([。！？!?；;])(?=[^\n])/g, "$1\n")
    .replace(/([，、：:])(?=[^\n]{26,})/g, "$1\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function renderKeyword(text: string, key: string): ReactNode[] {
  return text.split(KEYWORDS).map((part, idx) => {
    if (!part) return null;
    if (part.match(KEYWORDS)) {
      let cls = "keyword-mainline";
      if (part.includes("恋爱")) cls = "keyword-romance";
      if (part.includes("神兽") || part.includes("危机")) cls = "keyword-epic";
      return (
        <span key={`${key}-kw-${idx}`} className={cls}>
          {part}
        </span>
      );
    }
    return <Fragment key={`${key}-tx-${idx}`}>{part}</Fragment>;
  });
}

function renderInlineMarkdown(line: string, key: string): ReactNode[] {
  const segments = line
    .split(/(\*\*[^*\n][\s\S]*?\*\*|__[^_\n][\s\S]*?__|\*[^*\n][\s\S]*?\*|_[^_\n][\s\S]*?_|~~[^~\n][\s\S]*?~~)/g)
    .filter(Boolean);

  return segments.map((segment, idx) => {
    const baseKey = `${key}-${idx}`;
    if (/^\*\*[\s\S]+\*\*$/.test(segment)) {
      return (
        <strong key={baseKey} className="font-bold text-white">
          {renderKeyword(segment.slice(2, -2), baseKey)}
        </strong>
      );
    }
    if (/^__[\s\S]+__$/.test(segment)) {
      return (
        <strong key={baseKey} className="font-bold underline decoration-[#7c5cff] decoration-2">
          {renderKeyword(segment.slice(2, -2), baseKey)}
        </strong>
      );
    }
    if (/^\*[^*\n][\s\S]*\*$/.test(segment)) {
      return (
        <em key={baseKey} className="italic text-[#d2e5ff]">
          {renderKeyword(segment.slice(1, -1), baseKey)}
        </em>
      );
    }
    if (/^_[^_\n][\s\S]*_$/.test(segment)) {
      return (
        <em key={baseKey} className="italic text-[#d2e5ff]">
          {renderKeyword(segment.slice(1, -1), baseKey)}
        </em>
      );
    }
    if (/^~~[\s\S]+~~$/.test(segment)) {
      return (
        <span key={baseKey} className="line-through opacity-75">
          {renderKeyword(segment.slice(2, -2), baseKey)}
        </span>
      );
    }
    return <Fragment key={baseKey}>{renderKeyword(segment, baseKey)}</Fragment>;
  });
}

function renderNarrative(text: string): ReactNode {
  const readable = smartBreak(sanitizeAssistantText(text));
  const lines = readable.split("\n");

  return (
    <div className="prose-rp">
      {lines.map((line, idx) => {
        if (!line.trim()) {
          return <div key={`line-empty-${idx}`} className="h-2" />;
        }
        const isSection = /^\[.+\]|^【.+】/.test(line.trim());
        return (
          <p key={`line-${idx}`} className={cn("message-enter", isSection && "font-semibold text-white")}>
            {renderInlineMarkdown(line, `inline-${idx}`)}
          </p>
        );
      })}
    </div>
  );
}

const optionClassByIndex = [
  "from-[#4da3ff] to-[#217dff]",
  "from-[#7c5cff] to-[#9355ff]",
  "from-[#37d6c8] to-[#1fb6a8]",
  "from-[#ffb347] to-[#ff9435]",
  "from-[#ff5c7a] to-[#ff4ca0]",
  "from-[#8ad96b] to-[#4ab74c]",
];

export default function ChatStreamView({ messages, onOptionClick }: Props) {
  return (
    <div className="space-y-3">
      {messages.map((msg) => {
        const isOpening = msg.role === "assistant" && (msg.turnIndex ?? 0) === 1;
        return (
          <Card
            key={msg.id}
            className={cn(
              "message-enter border",
              msg.role === "user"
                ? "border-[#4f7bc6] bg-[linear-gradient(145deg,rgba(15,36,74,.9),rgba(12,26,54,.96))]"
                : "border-[#3f4f7f] bg-[linear-gradient(145deg,rgba(26,25,50,.9),rgba(18,20,39,.96))]",
              isOpening &&
                "border-[#5cc8ff] bg-[linear-gradient(145deg,rgba(17,39,84,.95),rgba(16,29,63,.97))] shadow-[0_0_24px_rgba(92,200,255,.18)]",
            )}
          >
            {isOpening ? (
              <div className="mb-2 inline-flex items-center rounded-full border border-[#5cc8ff]/60 bg-[#122f68] px-3 py-1 text-xs font-semibold text-[#d9efff]">
                开场剧情
              </div>
            ) : null}
          <div className="mb-2 flex items-center gap-2">
            <Badge variant={msg.role === "user" ? "primary" : "violet"}>{msg.role}</Badge>
            {msg.turnIndex ? <span className="text-xs text-[#8ea5cd]">Turn {msg.turnIndex}</span> : null}
          </div>

          {msg.role === "assistant" ? (
            <div>{renderNarrative(msg.text)}</div>
          ) : (
            <p className="whitespace-pre-wrap text-[15px] leading-7 text-[#eaf2ff]">{msg.text}</p>
          )}

          {msg.role === "assistant" && msg.actionOptions && msg.actionOptions.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {msg.actionOptions.slice(0, 6).map((opt, index) => (
                <Button
                  key={`${msg.id}-${opt.id}`}
                  variant="chip"
                  size="sm"
                  className={cn("bg-gradient-to-r", optionClassByIndex[index % optionClassByIndex.length])}
                  onClick={() => onOptionClick?.(opt)}
                >
                  {opt.text}
                </Button>
              ))}
            </div>
          ) : null}
          </Card>
        );
      })}
    </div>
  );
}
