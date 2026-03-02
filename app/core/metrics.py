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


def snapshot_summary() -> dict[str, float]:
    requests_total = 0.0
    requests_5xx_total = 0.0
    vector_hits_total = 0.0
    timeline_hits_total = 0.0
    turns_created_total = 0.0
    conflicts_total = 0.0
    provider_latency_sum = 0.0
    provider_latency_count = 0.0

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

    provider_latency_ms_avg = (
        (provider_latency_sum / provider_latency_count) * 1000 if provider_latency_count else 0.0
    )
    return {
        "requests_total": requests_total,
        "requests_5xx_total": requests_5xx_total,
        "provider_latency_ms_avg": provider_latency_ms_avg,
        "vector_hits_total": vector_hits_total,
        "timeline_hits_total": timeline_hits_total,
        "turns_created_total": turns_created_total,
        "conflicts_total": conflicts_total,
    }
