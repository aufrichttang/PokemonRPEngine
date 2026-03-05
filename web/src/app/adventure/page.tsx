"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpenText,
  ChevronDown,
  Flame,
  Package,
  Save,
  ScrollText,
  Shield,
} from "lucide-react";
import { toast } from "sonner";
import ChatStreamView, { type ChatBubble } from "@/components/chat/ChatStreamView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Drawer } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  createGameSlot,
  getGameFactions,
  getGameLore,
  getGameSlot,
  getGameTime,
  listGameSlots,
  streamGameAction,
  streamGameTurn,
} from "@/lib/api/endpoints";
import type {
  ActionOptionV2,
  ApiError,
  GameSlot,
  GameSlotItem,
  GameTurnResponse,
  StoryChapter,
} from "@/lib/schemas/types";

type Pace = "fast" | "balanced" | "epic";

type CreateStage = "idle" | "creating_world" | "enhancing_story" | "opening_ready" | "failed";

type CreateForm = {
  slot_name: string;
  world_seed: string;
  canon_gen: number;
  canon_game: string;
  name: string;
  gender: string;
  age: string;
  height_cm: string;
  appearance: string;
  personality: string;
  background: string;
  detail: string;
};

const WINDOW_SIZE = 72;
const paceConfig = {
  fast: { label: "Fast", note: "更快推进" },
  balanced: { label: "Balanced", note: "剧情平衡" },
  epic: { label: "Epic", note: "更浓叙事" },
} as const;

function makeClientTurnId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `ct-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (err && typeof err === "object") {
    const apiErr = err as Partial<ApiError>;
    if (typeof apiErr.message === "string" && apiErr.message) {
      return apiErr.trace_id
        ? `${apiErr.message} (trace=${apiErr.trace_id})`
        : `${apiErr.message}${apiErr.code ? ` (code=${apiErr.code})` : ""}`;
    }
  }
  return "未知错误";
}

function toActionOptions(options?: ActionOptionV2[]): ActionOptionV2[] {
  if (!Array.isArray(options)) return [];
  return options
    .map((opt) => ({
      id: String(opt.id ?? "").trim(),
      text: String(opt.text ?? "").trim(),
      send_text: String(opt.send_text ?? opt.text ?? "").trim(),
    }))
    .filter((item) => item.id && item.send_text && item.text);
}

function normalizeNarrative(payload: GameTurnResponse): string {
  const primary = payload.narrative?.primary?.trim() || payload.assistant_text?.trim() || "";
  const detail = payload.narrative?.detail?.trim();
  if (detail && detail !== primary) {
    return `${primary}\n\n${detail}`;
  }
  return primary;
}

function buildBubbles(slot?: GameSlot): ChatBubble[] {
  if (!slot) return [];
  const rows: ChatBubble[] = [];
  for (const turn of slot.turns || []) {
    rows.push({
      id: `${turn.turn_id}-u`,
      role: "user",
      text: turn.user_text,
      turnIndex: turn.turn_index,
    });
    rows.push({
      id: `${turn.turn_id}-a`,
      role: "assistant",
      text: turn.narrative?.detail
        ? `${turn.narrative.primary || turn.assistant_text}\n\n${turn.narrative.detail}`
        : turn.narrative?.primary || turn.assistant_text || "",
      turnIndex: turn.turn_index,
      actionOptions: toActionOptions(turn.action_options),
    });
  }
  return rows;
}

function flattenChapters(slot?: GameSlot): StoryChapter[] {
  const acts = slot?.world_profile?.story_blueprint?.acts || [];
  return acts.flatMap((act) => act.chapters || []);
}

function getTaskSlice(slot?: GameSlot): StoryChapter[] {
  const chapters = flattenChapters(slot);
  if (!chapters.length) return [];
  const currentIndex = chapters.findIndex(
    (chapter) =>
      chapter.act_index === (slot?.story_progress?.act || 1) &&
      chapter.chapter_index === (slot?.story_progress?.chapter || 1),
  );
  if (currentIndex < 0) return chapters.slice(0, 5);
  const start = Math.max(0, currentIndex - 1);
  return chapters.slice(start, start + 5);
}

function summarizeInventory(slot?: GameSlot) {
  const inventory = slot?.inventory || {};
  return Object.entries(inventory).map(([category, rows]) => ({
    category,
    total: (rows || []).reduce((acc, item) => acc + (item.count || 0), 0),
    rows: rows || [],
  }));
}

export default function AdventurePage() {
  const queryClient = useQueryClient();
  const chatRef = useRef<HTMLDivElement | null>(null);

  const [selectedSlotId, setSelectedSlotId] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [showAllMessages, setShowAllMessages] = useState(false);
  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [input, setInput] = useState("");
  const [pace, setPace] = useState<Pace>("balanced");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [shouldFollowBottom, setShouldFollowBottom] = useState(true);
  const [createStage, setCreateStage] = useState<CreateStage>("idle");
  const [openingHint, setOpeningHint] = useState<string>("");
  const [debugOpen, setDebugOpen] = useState(false);

  const [form, setForm] = useState<CreateForm>({
    slot_name: "新冒险",
    world_seed: "",
    canon_gen: 9,
    canon_game: "sv",
    name: "",
    gender: "",
    age: "",
    height_cm: "",
    appearance: "",
    personality: "",
    background: "",
    detail: "",
  });

  const debugEnabled = process.env.NEXT_PUBLIC_RP_DEV_DEBUG_UI === "true";

  const slotsQuery = useQuery({
    queryKey: ["v2-slots"],
    queryFn: () => listGameSlots(1, 100),
    staleTime: 10_000,
  });

  const slotQuery = useQuery({
    queryKey: ["v2-slot", selectedSlotId],
    queryFn: () => getGameSlot(selectedSlotId),
    enabled: Boolean(selectedSlotId),
    staleTime: 2_500,
  });

  const loreQuery = useQuery({
    queryKey: ["v2-slot-lore", selectedSlotId],
    queryFn: () => getGameLore(selectedSlotId),
    enabled: debugEnabled && debugOpen && Boolean(selectedSlotId),
    staleTime: 4_000,
  });

  const timeQuery = useQuery({
    queryKey: ["v2-slot-time", selectedSlotId],
    queryFn: () => getGameTime(selectedSlotId),
    enabled: debugEnabled && debugOpen && Boolean(selectedSlotId),
    staleTime: 4_000,
  });

  const factionQuery = useQuery({
    queryKey: ["v2-slot-factions", selectedSlotId],
    queryFn: () => getGameFactions(selectedSlotId),
    enabled: debugEnabled && debugOpen && Boolean(selectedSlotId),
    staleTime: 4_000,
  });

  useEffect(() => {
    const rows = slotsQuery.data || [];
    if (!selectedSlotId && rows.length) {
      setSelectedSlotId(rows[0].slot_id);
    }
  }, [slotsQuery.data, selectedSlotId]);

  useEffect(() => {
    setMessages(buildBubbles(slotQuery.data));
    setShowAllMessages(false);
  }, [slotQuery.data]);

  useEffect(() => {
    if (!chatRef.current || !shouldFollowBottom) return;
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, shouldFollowBottom]);

  const createMutation = useMutation({
    mutationFn: async () =>
      createGameSlot({
        slot_name: form.slot_name || "新冒险",
        world_seed: form.world_seed || null,
        canon_gen: Number(form.canon_gen || 9),
        canon_game: form.canon_game || null,
        player_profile: {
          name: form.name || undefined,
          gender: form.gender || undefined,
          age: form.age ? Number(form.age) : undefined,
          height_cm: form.height_cm ? Number(form.height_cm) : undefined,
          appearance: form.appearance || undefined,
          personality: form.personality || undefined,
          background: form.background || undefined,
          detail: form.detail || undefined,
        },
      }),
    onMutate: () => {
      setCreateStage("creating_world");
      setErrorText("");
    },
    onSuccess: (slot) => {
      setCreateStage("opening_ready");
      setShowCreate(false);
      setSelectedSlotId(slot.slot_id);
      setOpeningHint(`【章节开场】${slot.story_progress.objective}`);
      toast.success("新存档已创建", {
        description: `${slot.slot_name} · ${slot.world_profile.continent_name} · ${slot.world_profile.start_town}`,
      });
      void queryClient.invalidateQueries({ queryKey: ["v2-slots"] });
      void queryClient.invalidateQueries({ queryKey: ["v2-slot", slot.slot_id] });
      setTimeout(() => setCreateStage("idle"), 1200);
    },
    onError: (error) => {
      const msg = toErrorMessage(error);
      setErrorText(msg);
      setCreateStage("failed");
      toast.error("创建存档失败", { description: msg });
    },
  });

  useEffect(() => {
    if (!createMutation.isPending) return;
    const timer = setTimeout(() => setCreateStage("enhancing_story"), 1800);
    return () => clearTimeout(timer);
  }, [createMutation.isPending]);

  const currentSlot = slotQuery.data;
  const taskRows = useMemo(() => getTaskSlice(currentSlot), [currentSlot]);
  const inventoryGroups = useMemo(() => summarizeInventory(currentSlot), [currentSlot]);

  const visibleMessages = useMemo(() => {
    if (showAllMessages) return messages;
    if (messages.length <= WINDOW_SIZE) return messages;
    return messages.slice(messages.length - WINDOW_SIZE);
  }, [messages, showAllMessages]);
  const hiddenCount = Math.max(0, messages.length - visibleMessages.length);

  async function applyTurn(
    runner: () => Promise<GameTurnResponse>,
    userText: string,
    assistantId: string,
    previousState: Record<string, unknown> = {},
  ) {
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", text: userText },
      { id: assistantId, role: "assistant", text: "" },
    ]);

    const done = await runner();
    const mergedText = normalizeNarrative(done);

    setMessages((prev) =>
      prev.map((item) =>
        item.id === assistantId
          ? {
              ...item,
              text: mergedText,
              actionOptions: toActionOptions(done.action_options),
            }
          : item,
      ),
    );

    const snapshot = done.state_snapshot || {};
    const oldLocation = String(previousState.location ?? "").trim();
    const newLocation = String(snapshot.location ?? "").trim();
    if (newLocation && newLocation !== oldLocation) {
      toast.message("位置更新", { description: `${oldLocation || "未知"} → ${newLocation}` });
    }

    const oldMoney = Number(previousState.money ?? 0);
    const newMoney = Number(snapshot.money ?? oldMoney);
    if (Number.isFinite(newMoney) && newMoney !== oldMoney) {
      const delta = newMoney - oldMoney;
      toast.message("资源变化", {
        description: `金币 ${delta >= 0 ? `+${delta}` : delta}`,
      });
    }

    const oldBadges = Array.isArray(previousState.badges) ? previousState.badges.length : 0;
    const newBadges = Array.isArray(snapshot.badges) ? snapshot.badges.length : oldBadges;
    if (newBadges > oldBadges) {
      toast.success("徽章增加", { description: `总徽章数 ${newBadges}` });
    }

    void queryClient.invalidateQueries({ queryKey: ["v2-slot", selectedSlotId] });
  }

  async function handleSend(rawText: string) {
    const content = rawText.trim();
    if (!selectedSlotId || !content || submitting) return;

    const assistantId = `a-${Date.now()}`;
    const previousState = (currentSlot?.turns || []).at(-1)?.state_snapshot || {};

    setSubmitting(true);
    setErrorText("");
    setInput("");

    try {
      await applyTurn(
        () =>
          streamGameTurn(
            selectedSlotId,
            content,
            {
              onPrimary: (text) => {
                setMessages((prev) =>
                  prev.map((item) => (item.id === assistantId ? { ...item, text } : item)),
                );
              },
              onDelta: (delta) => {
                setMessages((prev) =>
                  prev.map((item) =>
                    item.id === assistantId ? { ...item, text: `${item.text || ""}${delta}` } : item,
                  ),
                );
              },
            },
            "zh",
            pace,
            makeClientTurnId(),
          ),
        content,
        assistantId,
        previousState,
      );
    } catch (error) {
      const msg = toErrorMessage(error);
      setErrorText(msg);
      setMessages((prev) =>
        prev.map((item) =>
          item.id === assistantId ? { ...item, text: `【系统提示】${msg}` } : item,
        ),
      );
      toast.error("回合执行失败", { description: msg });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleActionClick(action: ActionOptionV2) {
    if (!selectedSlotId || submitting) return;
    const content = action.send_text?.trim() || action.text?.trim();
    if (!content) return;

    const assistantId = `a-${Date.now()}`;
    const previousState = (currentSlot?.turns || []).at(-1)?.state_snapshot || {};

    setSubmitting(true);
    setErrorText("");

    try {
      await applyTurn(
        () =>
          streamGameAction(
            selectedSlotId,
            action.id,
            {
              onPrimary: (text) => {
                setMessages((prev) =>
                  prev.map((item) => (item.id === assistantId ? { ...item, text } : item)),
                );
              },
              onDelta: (delta) => {
                setMessages((prev) =>
                  prev.map((item) =>
                    item.id === assistantId ? { ...item, text: `${item.text || ""}${delta}` } : item,
                  ),
                );
              },
            },
            "zh",
            pace,
            makeClientTurnId(),
          ),
        content,
        assistantId,
        previousState,
      );
    } catch (error) {
      const msg = toErrorMessage(error);
      setErrorText(msg);
      setMessages((prev) =>
        prev.map((item) =>
          item.id === assistantId ? { ...item, text: `【系统提示】${msg}` } : item,
        ),
      );
      toast.error("动作执行失败", { description: msg });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="game-shell">
      <aside className="space-y-4">
        <Card className="panel-glow">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h1 className="title-display text-3xl text-[#d9e9ff]">Pokemon RP</h1>
              <p className="text-sm text-[#8ba5ce]">JRPG 沉浸冒险端</p>
            </div>
            <Badge variant="violet">V2.5</Badge>
          </div>

          <Button className="w-full" onClick={() => setShowCreate((v) => !v)}>
            <Save className="mr-2 h-4 w-4" />
            {showCreate ? "收起创建" : "新建存档"}
          </Button>

          {showCreate ? (
            <div className="mt-3 space-y-2">
              <Input
                value={form.slot_name}
                onChange={(e) => setForm((prev) => ({ ...prev, slot_name: e.target.value }))}
                placeholder="存档名"
              />
              <Input
                value={form.world_seed}
                onChange={(e) => setForm((prev) => ({ ...prev, world_seed: e.target.value }))}
                placeholder="世界种子（可空）"
              />

              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={String(form.canon_gen)}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, canon_gen: Number(e.target.value || 9) }))
                  }
                  placeholder="世代"
                />
                <Input
                  value={form.canon_game}
                  onChange={(e) => setForm((prev) => ({ ...prev, canon_game: e.target.value }))}
                  placeholder="版本"
                />
              </div>

              <Input
                value={form.name}
                onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="角色名（可空自动生成）"
              />

              <div className="grid grid-cols-3 gap-2">
                <Input
                  value={form.gender}
                  onChange={(e) => setForm((prev) => ({ ...prev, gender: e.target.value }))}
                  placeholder="性别"
                />
                <Input
                  value={form.age}
                  onChange={(e) => setForm((prev) => ({ ...prev, age: e.target.value }))}
                  placeholder="年龄"
                />
                <Input
                  value={form.height_cm}
                  onChange={(e) => setForm((prev) => ({ ...prev, height_cm: e.target.value }))}
                  placeholder="身高"
                />
              </div>

              <Textarea
                rows={2}
                value={form.appearance}
                onChange={(e) => setForm((prev) => ({ ...prev, appearance: e.target.value }))}
                placeholder="外形特征"
              />
              <Textarea
                rows={2}
                value={form.personality}
                onChange={(e) => setForm((prev) => ({ ...prev, personality: e.target.value }))}
                placeholder="性格"
              />
              <Textarea
                rows={2}
                value={form.background}
                onChange={(e) => setForm((prev) => ({ ...prev, background: e.target.value }))}
                placeholder="背景经历"
              />
              <Textarea
                rows={2}
                value={form.detail}
                onChange={(e) => setForm((prev) => ({ ...prev, detail: e.target.value }))}
                placeholder="补充细节"
              />

              <Button
                className="w-full"
                disabled={createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                {createMutation.isPending ? "创建中..." : "创建并开场"}
              </Button>

              {createStage !== "idle" ? (
                <p className="text-xs text-[#9eb4d8]">
                  {createStage === "creating_world" && "正在生成大陆与开场骨架..."}
                  {createStage === "enhancing_story" && "正在增强主线叙事，请稍候..."}
                  {createStage === "opening_ready" && "开场就绪，正在进入冒险..."}
                  {createStage === "failed" && "创建失败，请修正输入或稍后重试。"}
                </p>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Card className="panel-glow">
          <CardTitle>存档列表</CardTitle>
          <CardDescription>点击切换你的冒险进度</CardDescription>
          <div className="mt-3 max-h-[46vh] space-y-2 overflow-y-auto pr-1">
            {(slotsQuery.data || []).map((slot: GameSlotItem) => (
              <button
                key={slot.slot_id}
                onClick={() => setSelectedSlotId(slot.slot_id)}
                className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                  selectedSlotId === slot.slot_id
                    ? "border-[#4da3ff] bg-[#183264]"
                    : "border-[#314b79] bg-[#101f3f] hover:border-[#4d6da3] hover:bg-[#14284f]"
                }`}
              >
                <p className="font-semibold text-[#ecf4ff]">{slot.slot_name}</p>
                <p className="text-xs text-[#89a2ca]">Seed: {slot.world_seed || "-"}</p>
              </button>
            ))}
          </div>
        </Card>

        <Card className="panel-glow">
          <CardTitle>章节任务</CardTitle>
          <CardDescription>主线牵引，避免跑偏</CardDescription>
          <div className="mt-3 space-y-2">
            {taskRows.length ? (
              taskRows.map((task) => (
                <div
                  key={`${task.act_index}-${task.chapter_index}`}
                  className="rounded-xl border border-[#314b79] bg-[#11264a] p-2"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <p className="text-sm font-semibold text-[#e8f2ff]">
                      第{task.act_index}幕·第{task.chapter_index}章 {task.title}
                    </p>
                    <Badge variant={task.status === "completed" ? "green" : task.status === "active" ? "primary" : "default"}>
                      {task.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-[#9eb4d8]">目标：{task.objective}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-[#91a9cf]">当前无章节蓝图，先推进主线触发剧情。</p>
            )}
          </div>
        </Card>
      </aside>

      <main className="space-y-4">
        <Card className="panel-glow">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="title-display text-3xl text-[#d9e9ff]">
                {currentSlot?.slot_name || "请选择或创建存档"}
              </h2>
              <p className="mt-1 text-sm text-[#9ab2d7]">
                第 {currentSlot?.story_progress?.act || 1} 幕 · 第 {currentSlot?.story_progress?.chapter || 1} 章 · {" "}
                {currentSlot?.story_progress?.objective || "推进主线"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="orange">风险: {currentSlot?.story_progress?.risk_level || "medium"}</Badge>
              <Badge variant="primary">位置: {String((currentSlot?.turns || []).at(-1)?.state_snapshot?.location || currentSlot?.world_profile?.start_town || "未知")}</Badge>
              <Badge variant="violet">
                World Tension: {currentSlot?.lore_kernel_summary?.cycle_instability ?? 0}
              </Badge>
              <Badge variant="green">
                Narrative Stability: {currentSlot?.time_kernel_summary?.narrative_cohesion ?? 0}
              </Badge>
              {debugEnabled ? (
                <Button variant="secondary" size="sm" onClick={() => setDebugOpen(true)}>
                  <Shield className="mr-1 h-4 w-4" /> 调试
                </Button>
              ) : null}
            </div>
          </div>
        </Card>

        {openingHint ? (
          <Card className="border-[#4d6ea8] bg-[linear-gradient(150deg,rgba(27,51,92,.95),rgba(16,29,58,.95))]">
            <div className="flex items-start gap-3">
              <ScrollText className="mt-1 h-5 w-5 text-[#9fd1ff]" />
              <div>
                <p className="text-sm font-semibold text-[#eaf4ff]">开场已生成</p>
                <p className="text-sm text-[#b7cbed]">{openingHint}</p>
              </div>
            </div>
          </Card>
        ) : null}

        <Card className="panel-glow">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-[#9eb3d7]">
              <BookOpenText className="h-4 w-4" /> 剧情舞台
            </div>
            <div className="flex items-center gap-2">
              {hiddenCount > 0 ? (
                <Button variant="ghost" size="sm" onClick={() => setShowAllMessages(true)}>
                  展开更早 {hiddenCount} 条
                </Button>
              ) : null}
              <Badge variant="default">{messages.length} 条</Badge>
            </div>
          </div>

          <div
            className="story-scroll"
            ref={chatRef}
            onScroll={(e) => {
              const el = e.currentTarget;
              const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
              setShouldFollowBottom(nearBottom);
            }}
          >
            <ChatStreamView messages={visibleMessages} onOptionClick={handleActionClick} />
          </div>

          <div className="input-panel mt-3 rounded-2xl border border-[#315186] bg-[#0b1838]/90 p-3">
            {errorText ? (
              <div className="mb-2 rounded-lg border border-[#8d3f5c] bg-[#512038]/30 px-3 py-2 text-sm text-[#ffd5e5]">
                <AlertTriangle className="mr-1 inline h-4 w-4" />
                {errorText}
              </div>
            ) : null}

            <div className="mb-2 flex flex-wrap items-center gap-2">
              {(Object.keys(paceConfig) as Pace[]).map((item) => (
                <button
                  key={item}
                  onClick={() => setPace(item)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                    pace === item
                      ? "bg-[#4da3ff] text-white"
                      : "bg-[#112750] text-[#9ab5de] hover:bg-[#1a3465]"
                  }`}
                >
                  {paceConfig[item].label} · {paceConfig[item].note}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={3}
                placeholder="输入动作或对话。Enter 发送，Shift+Enter 换行"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleSend(input);
                  }
                }}
              />
              <Button className="h-auto min-w-24" disabled={submitting} onClick={() => void handleSend(input)}>
                {submitting ? (
                  <span className="inline-flex items-center gap-1">
                    <Flame className="h-4 w-4 animate-pulse" /> 处理中
                  </span>
                ) : (
                  "发送"
                )}
              </Button>
            </div>
          </div>
        </Card>
      </main>

      <aside className="game-right space-y-4">
        <Card className="panel-glow">
          <div className="mb-2 flex items-center justify-between">
            <CardTitle>当前队伍</CardTitle>
            <Badge variant="primary">{currentSlot?.party?.length || 0}/6</Badge>
          </div>
          <div className="space-y-2">
            {(currentSlot?.party || []).map((member) => (
              <div
                key={`${member.position}-${member.slug_id}`}
                className="rounded-xl border border-[#315084] bg-[#102449] px-3 py-2"
              >
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-[#edf4ff]">
                    #{member.position} {member.name_zh}
                  </p>
                  <Badge variant="default">Lv.{member.level}</Badge>
                </div>
                <p className="text-xs text-[#97b0d8]">{member.types.join(" / ")}</p>
              </div>
            ))}
            {!currentSlot?.party?.length ? <p className="text-sm text-[#90a9cf]">暂无队伍信息</p> : null}
          </div>
        </Card>

        <Card className="panel-glow">
          <div className="mb-2 flex items-center justify-between">
            <CardTitle>宝可梦仓库</CardTitle>
            <Badge variant="violet">{currentSlot?.storage_box?.length || 0}</Badge>
          </div>
          <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
            {(currentSlot?.storage_box || []).map((member, index) => (
              <div
                key={`${member.slug_id}-${index}`}
                className="flex items-center justify-between rounded-lg border border-[#2c4a7c] bg-[#101f41] px-3 py-2 text-sm"
              >
                <span>{member.name_zh}</span>
                <span className="text-[#8eabd8]">Lv.{member.level}</span>
              </div>
            ))}
            {!currentSlot?.storage_box?.length ? <p className="text-sm text-[#90a9cf]">仓库为空</p> : null}
          </div>
        </Card>

        <Card className="panel-glow">
          <div className="mb-2 flex items-center justify-between">
            <CardTitle>背包</CardTitle>
            <Badge variant="green">
              <Package className="mr-1 h-3 w-3" />
              {inventoryGroups.reduce((acc, group) => acc + group.total, 0)}
            </Badge>
          </div>
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {inventoryGroups.length ? (
              inventoryGroups.map((group) => (
                <details key={group.category} className="rounded-xl border border-[#2f4e84] bg-[#102248] p-2" open>
                  <summary className="cursor-pointer list-none text-sm font-semibold text-[#d5e7ff]">
                    <div className="flex items-center justify-between">
                      <span className="inline-flex items-center gap-2">
                        <ChevronDown className="h-4 w-4" />
                        {group.category}
                      </span>
                      <span className="text-xs text-[#9ab2d8]">{group.total}</span>
                    </div>
                  </summary>
                  <div className="mt-2 space-y-1">
                    {group.rows.map((item, idx) => (
                      <div key={`${group.category}-${idx}`} className="mini-row flex items-center justify-between text-sm">
                        <span>{item.name_zh}</span>
                        <span className="text-[#9db3d8]">x{item.count}</span>
                      </div>
                    ))}
                  </div>
                </details>
              ))
            ) : (
              <p className="text-sm text-[#90a9cf]">背包为空</p>
            )}
          </div>
        </Card>
      </aside>

      {debugEnabled ? (
        <Drawer open={debugOpen} onOpenChange={setDebugOpen} title="开发调试抽屉">
          <div className="space-y-4">
            <Card>
              <CardTitle>Kernel 摘要</CardTitle>
              <CardDescription>仅开发模式展示</CardDescription>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-[#a9bce0]">
                {JSON.stringify(
                  {
                    lore: loreQuery.data?.lore_kernel || currentSlot?.lore_kernel_summary || {},
                    time: timeQuery.data?.time_kernel || currentSlot?.time_kernel_summary || {},
                    factions: factionQuery.data?.faction_kernel || currentSlot?.faction_kernel_summary || {},
                    warnings: currentSlot?.active_warnings || [],
                  },
                  null,
                  2,
                )}
              </pre>
            </Card>
            <Card>
              <CardTitle>最近回合</CardTitle>
              <CardDescription>性能与状态快照</CardDescription>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-[#a9bce0]">
                {JSON.stringify((currentSlot?.turns || []).slice(-2), null, 2)}
              </pre>
            </Card>
          </div>
        </Drawer>
      ) : null}
    </div>
  );
}
