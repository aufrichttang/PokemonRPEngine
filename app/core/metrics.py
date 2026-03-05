from __future__ import annotations

from prometheus_client import REGISTRY, Counter, Histogram

rp_requests_total = Counter(
    "rp_requests_total",
    "Total requests for rp engine",
    ["path", "method", "status"],
)

rp_provider_latency_seconds = Histogram(
    "rp_provider_latency_seconds",
    "Provider latency in seconds",
    ["provider"],
)

rp_retrieval_vector_hits_total = Counter(
    "rp_retrieval_vector_hits_total",
    "Total vector retrieval hits",
)

rp_retrieval_timeline_hits_total = Counter(
    "rp_retrieval_timeline_hits_total",
    "Total timeline retrieval hits",
)

rp_turns_created_total = Counter(
    "rp_turns_created_total",
    "Total turns created",
)

rp_conflicts_total = Counter(
    "rp_conflicts_total",
    "Total detected memory conflicts",
)

rp_option_final_latency_ms = Histogram(
    "rp_option_final_latency_ms",
    "Latency from request start to final action options emitted (ms)",
    buckets=(200, 400, 800, 1200, 2000, 5000, 10000, 20000, 40000),
)

rp_turn_first_interactive_seconds = Histogram(
    "rp_turn_first_interactive_seconds",
    "Latency from request start to first interactive options event (seconds)",
    buckets=(0.2, 0.4, 0.8, 1.2, 2.0, 3.0, 5.0, 8.0, 15.0),
)

rp_turn_done_seconds = Histogram(
    "rp_turn_done_seconds",
    "Latency from request start to done event (seconds)",
    buckets=(1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 40.0),
)

rp_provider_planner_latency_seconds = Histogram(
    "rp_provider_planner_latency_seconds",
    "Planner-stage provider latency in seconds",
    ["provider"],
)

rp_provider_narrative_latency_seconds = Histogram(
    "rp_provider_narrative_latency_seconds",
    "Narrative-stage provider latency in seconds",
    ["provider"],
)

rp_planner_timeout_fallback_total = Counter(
    "rp_planner_timeout_fallback_total",
    "Total planner timeout fallbacks",
)


def snapshot_summary() -> dict[str, float]:
    requests_total = 0.0
    requests_5xx_total = 0.0
    vector_hits_total = 0.0
    timeline_hits_total = 0.0
    turns_created_total = 0.0
    conflicts_total = 0.0
    option_final_latency_ms_avg = 0.0
    turn_first_interactive_ms_avg = 0.0
    turn_done_ms_avg = 0.0
    planner_latency_ms_avg = 0.0
    narrative_latency_ms_avg = 0.0
    planner_timeout_fallback_total = 0.0
    provider_latency_sum = 0.0
    provider_latency_count = 0.0
    option_final_sum = 0.0
    option_final_count = 0.0
    first_interactive_sum = 0.0
    first_interactive_count = 0.0
    turn_done_sum = 0.0
    turn_done_count = 0.0
    planner_latency_sum = 0.0
    planner_latency_count = 0.0
    narrative_latency_sum = 0.0
    narrative_latency_count = 0.0

    for metric in REGISTRY.collect():
        if metric.name == "rp_requests_total":
            for sample in metric.samples:
                if sample.name != "rp_requests_total":
                    continue
                value = float(sample.value)
                requests_total += value
                if str(sample.labels.get("status", "")).startswith("5"):
                    requests_5xx_total += value
        elif metric.name == "rp_retrieval_vector_hits_total":
            for sample in metric.samples:
                if sample.name == "rp_retrieval_vector_hits_total":
                    vector_hits_total += float(sample.value)
        elif metric.name == "rp_retrieval_timeline_hits_total":
            for sample in metric.samples:
                if sample.name == "rp_retrieval_timeline_hits_total":
                    timeline_hits_total += float(sample.value)
        elif metric.name == "rp_turns_created_total":
            for sample in metric.samples:
                if sample.name == "rp_turns_created_total":
                    turns_created_total += float(sample.value)
        elif metric.name == "rp_conflicts_total":
            for sample in metric.samples:
                if sample.name == "rp_conflicts_total":
                    conflicts_total += float(sample.value)
        elif metric.name == "rp_provider_latency_seconds":
            for sample in metric.samples:
                if sample.name == "rp_provider_latency_seconds_sum":
                    provider_latency_sum += float(sample.value)
                elif sample.name == "rp_provider_latency_seconds_count":
                    provider_latency_count += float(sample.value)
        elif metric.name == "rp_option_final_latency_ms":
            for sample in metric.samples:
                if sample.name == "rp_option_final_latency_ms_sum":
                    option_final_sum += float(sample.value)
                elif sample.name == "rp_option_final_latency_ms_count":
                    option_final_count += float(sample.value)
        elif metric.name == "rp_turn_first_interactive_seconds":
            for sample in metric.samples:
                if sample.name == "rp_turn_first_interactive_seconds_sum":
                    first_interactive_sum += float(sample.value)
                elif sample.name == "rp_turn_first_interactive_seconds_count":
                    first_interactive_count += float(sample.value)
        elif metric.name == "rp_turn_done_seconds":
            for sample in metric.samples:
                if sample.name == "rp_turn_done_seconds_sum":
                    turn_done_sum += float(sample.value)
                elif sample.name == "rp_turn_done_seconds_count":
                    turn_done_count += float(sample.value)
        elif metric.name == "rp_provider_planner_latency_seconds":
            for sample in metric.samples:
                if sample.name == "rp_provider_planner_latency_seconds_sum":
                    planner_latency_sum += float(sample.value)
                elif sample.name == "rp_provider_planner_latency_seconds_count":
                    planner_latency_count += float(sample.value)
        elif metric.name == "rp_provider_narrative_latency_seconds":
            for sample in metric.samples:
                if sample.name == "rp_provider_narrative_latency_seconds_sum":
                    narrative_latency_sum += float(sample.value)
                elif sample.name == "rp_provider_narrative_latency_seconds_count":
                    narrative_latency_count += float(sample.value)
        elif metric.name == "rp_planner_timeout_fallback_total":
            for sample in metric.samples:
                if sample.name == "rp_planner_timeout_fallback_total":
                    planner_timeout_fallback_total += float(sample.value)

    provider_latency_ms_avg = (
        (provider_latency_sum / provider_latency_count) * 1000 if provider_latency_count else 0.0
    )
    option_final_latency_ms_avg = (
        option_final_sum / option_final_count if option_final_count else 0.0
    )
    turn_first_interactive_ms_avg = (
        (first_interactive_sum / first_interactive_count) * 1000 if first_interactive_count else 0.0
    )
    turn_done_ms_avg = (turn_done_sum / turn_done_count) * 1000 if turn_done_count else 0.0
    planner_latency_ms_avg = (
        (planner_latency_sum / planner_latency_count) * 1000 if planner_latency_count else 0.0
    )
    narrative_latency_ms_avg = (
        (narrative_latency_sum / narrative_latency_count) * 1000 if narrative_latency_count else 0.0
    )
    return {
        "requests_total": requests_total,
        "requests_5xx_total": requests_5xx_total,
        "provider_latency_ms_avg": provider_latency_ms_avg,
        "vector_hits_total": vector_hits_total,
        "timeline_hits_total": timeline_hits_total,
        "turns_created_total": turns_created_total,
        "conflicts_total": conflicts_total,
        "option_final_latency_ms_avg": option_final_latency_ms_avg,
        "turn_first_interactive_ms_avg": turn_first_interactive_ms_avg,
        "turn_done_ms_avg": turn_done_ms_avg,
        "planner_latency_ms_avg": planner_latency_ms_avg,
        "narrative_latency_ms_avg": narrative_latency_ms_avg,
        "planner_timeout_fallback_total": planner_timeout_fallback_total,
    }
