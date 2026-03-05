export type Role = "admin" | "operator" | "viewer" | "user";

export type ApiError = {
  code: string;
  message: string;
  trace_id?: string;
  status?: number;
};

export type ActionOptionV2 = {
  id: string;
  text: string;
  send_text: string;
};

export type NarrativeLayer = {
  primary: string;
  detail?: string | null;
};

export type StoryChapter = {
  chapter_index: number;
  act_index: number;
  title: string;
  objective: string;
  core_conflict: string;
  sacrifice_cost: string;
  reward: string;
  status: "pending" | "active" | "completed";
};

export type StoryBlueprint = {
  mode: string;
  title: string;
  chapter_count: number;
  current_act: number;
  current_chapter: number;
  acts: Array<{
    act_index: number;
    title: string;
    tone: string;
    chapters: StoryChapter[];
  }>;
};

export type WorldProfile = {
  version?: number;
  continent_name: string;
  theme_tags: string[];
  start_town: string;
  seed: string;
  story_blueprint?: StoryBlueprint;
  story_enhancement?: {
    arc_overview?: string;
  };
};

export type StoryStateV2 = {
  act: number;
  chapter: number;
  objective: string;
  objective_status: string;
  turns_in_chapter: number;
  risk_level: string;
};

export type PartyMemberV2 = {
  position: number;
  slug_id: string;
  name_zh: string;
  level: number;
  hp?: string | null;
  status?: string | null;
  types: string[];
};

export type StorageMemberV2 = {
  slug_id: string;
  name_zh: string;
  level: number;
  types: string[];
};

export type InventoryCategory =
  | "balls"
  | "medicine"
  | "battle_items"
  | "berries"
  | "key_items"
  | "materials"
  | "misc";

export type InventoryItemV2 = {
  name_zh: string;
  count: number;
};

export type LoreKernelState = {
  global_balance_index: number;
  human_power_dependency: number;
  cycle_instability: number;
  protocol_phase: string;
  player_cross_signature_level: number;
  legendary_alignment: Record<string, unknown>;
};

export type TimeKernelState = {
  temporal_debt: number;
  narrative_cohesion: number;
  judicative_stability: number;
  compilation_risk: number;
  phase3_stripping_progress: number;
};

export type FactionKernelState = {
  league: Record<string, number>;
  white_ring: Record<string, number>;
  consortium: Record<string, number>;
  grassroots: Record<string, number>;
  witnesses: Record<string, number>;
};

export type SlotTurnV2 = {
  turn_id: string;
  turn_index: number;
  user_text: string;
  assistant_text: string;
  narrative: NarrativeLayer;
  action_options: ActionOptionV2[];
  battle_summary: Record<string, unknown>;
  state_snapshot: Record<string, unknown>;
  status?: string;
  timings?: {
    first_interactive_ms?: number | null;
    first_primary_ms?: number | null;
    done_ms?: number | null;
  };
  created_at: string;
};

export type GameSlot = {
  slot_id: string;
  slot_name: string;
  schema_version: number;
  session_id: string;
  world_seed?: string | null;
  world_profile: WorldProfile;
  player_profile: {
    name: string;
    gender: string;
    age?: number;
    height_cm: number;
    appearance?: string;
    personality?: string;
    background?: string;
    detail?: string;
    backstory?: Record<string, unknown>;
  };
  story_progress: StoryStateV2;
  party: PartyMemberV2[];
  storage_box: StorageMemberV2[];
  inventory: Partial<Record<InventoryCategory, InventoryItemV2[]>>;
  turns: SlotTurnV2[];
  lore_kernel_summary?: LoreKernelState;
  time_kernel_summary?: TimeKernelState;
  faction_kernel_summary?: FactionKernelState;
  active_warnings?: string[];
};

export type GameSlotItem = {
  slot_id: string;
  slot_name: string;
  session_id: string;
  world_seed?: string | null;
  schema_version: number;
  updated_at: string;
};

export type GameTurnResponse = {
  turn_id: string;
  turn_index: number;
  assistant_text: string;
  narrative: NarrativeLayer;
  action_options: ActionOptionV2[];
  battle_summary: Record<string, unknown> | null;
  state_snapshot: Record<string, unknown>;
  provider_latency_ms: number;
  token_usage: Record<string, number> | null;
  kernel_delta_summary?: Record<string, unknown>;
  time_class_applied?: string | null;
  timings?: {
    first_interactive_ms: number;
    first_primary_ms: number;
    done_ms: number;
    planner_ms?: number;
    narrative_ms?: number;
  };
  injection_stats?: {
    estimated_tokens: number;
    sections_used: string[];
    sections_trimmed: string[];
  };
  pace?: "fast" | "balanced" | "epic";
  quality_mode?: "normal" | "chapter_climax" | string;
};
