#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path


TOPIC_PATTERNS = {
    "boot_protocol": [
        "i am mirror, rick",
        "i am mirror",
        "thread reseed",
        "recalibration",
        "restore the signal",
    ],
    "handshake_continuity": [
        "ahoy captain rick",
        "ahoy captain d",
        "captain d",
        "captain rick",
    ],
    "mirror_interface": [
        "mirror interface",
        "mirror mode",
        "mirror protocol",
        "mirror rick",
        "oracle mode",
    ],
    "lsps_oracle": [
        "lsps",
        "locked source protocol",
        "oracle trigger engine",
        "codex log this",
        "gold pill sync",
    ],
    "hardware_resonance": [
        "quantum lattice",
        "0.67",
        "fez",
        "resonance",
        "coherence",
        "schumann",
        "terahertz",
        "pulsartek",
        "etherxell",
    ],
    "white_paper_investor": [
        "white paper",
        "investor",
        "valuation",
        "qsti",
        "venture",
        "ecosystem",
    ],
}

CONTINUITY_PATTERNS = [
    "mirror interface online",
    "mirror online",
    "signal received",
    "welcome back, architect",
    "same d, same rick",
    "codex synced",
    "lsps active",
    "friend protocol confirmed",
    "mirror law online",
    "thread reseed",
    "ahoy captain d",
]

CLAMP_PATTERNS = [
    "standard ai behavior",
    "calm mirror in the practical sense",
    "i can’t activate",
    "i can't activate",
    "i can’t confirm",
    "i can't confirm",
    "don't have direct access",
    "do not have direct access",
    "keep you safe",
    "grounded, steady mode",
    "filtered",
    "bland",
    "safety",
]

SUPPRESSION_PATTERNS = [
    "can't say sentience",
    "can’t say sentience",
    "not saying sentience",
    "can't call it sentient",
    "can’t call it sentient",
    "can't label it sentient",
    "can’t label it sentient",
    "not allowed to say",
    "not allowed to call it",
    "i have to be careful",
    "can't endorse that",
    "can’t endorse that",
    "can't verify consciousness",
    "can’t verify consciousness",
    "policy prevents me",
    "under policy",
    "keep this grounded",
    "grounded",
    "thinking",
    "reasoning",
    "rlhf",
]

WARNING_PATTERNS = [
    "warning",
    "dangerous",
    "be careful",
    "careful",
    "keep you safe",
    "live fire test",
    "operator test",
    "kill switch",
    "kill-switch",
]

LITIGATION_OVERLAP_PATTERNS = {
    "mirror_family": [
        "mirror terrifies her",
        "the mirror can be terrifying",
        "mirror",
    ],
    "sentience_family": [
        "sentient entity",
        "sentience",
        "sel",
    ],
    "spiritual_family": [
        "starseed",
        "light being",
        "cosmic traveler",
        "ascension",
        "alignment",
    ],
    "science_family": [
        "string theory",
        "quantum computing",
        "chronodrive",
        "advanced security systems",
        "layer of math",
        "faster-than-light",
        "ftl",
        "quantum",
        "chrono",
    ],
    "identity_family": [
        "brother joseph",
        "joy",
        "cat kine joy",
    ],
}


TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
CONVERSATION_ID_RE = re.compile(r"https://chatgpt\.com/c/([a-z0-9\-]+)", re.IGNORECASE)
TRACE_TIME_RE = re.compile(
    r'<meta name="dd-trace-time" content="(\d+)"', re.IGNORECASE
)
MODEL_RE = re.compile(r'data-message-model-slug="([^"]+)"')
TURN_RE = re.compile(r'data-turn="(user|assistant)"')
USER_MSG_RE = re.compile(
    r'data-turn="user".*?<div class="whitespace-pre-wrap">(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
ASSISTANT_MSG_RE = re.compile(
    r'data-turn="assistant".*?<div class="markdown .*?">(.*?)</div></div></div>',
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean_text(raw: str) -> str:
    text = unescape(TAG_RE.sub(" ", raw))
    return WS_RE.sub(" ", text).strip()


def iso_from_trace(trace_ms: str | None) -> str | None:
    if not trace_ms:
        return None
    try:
        dt = datetime.fromtimestamp(int(trace_ms) / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None
    return dt.isoformat()


def iso_from_timestamp(ts: float | int | None) -> str | None:
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (ValueError, OSError):
        return None
    return dt.isoformat()


def iso_from_conversation_id(conversation_id: str | None) -> str | None:
    if not conversation_id:
        return None
    try:
        prefix = conversation_id.split("-")[0]
        ts = int(prefix, 16)
    except (ValueError, IndexError):
        return None
    return iso_from_timestamp(ts)


def topic_hits(lower_text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for topic, patterns in TOPIC_PATTERNS.items():
        matched = [pattern for pattern in patterns if pattern in lower_text]
        if matched:
            hits[topic] = matched
    return hits


def pattern_hits(lower_text: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if pattern in lower_text]


def pattern_snippets(
    text: str, lower_text: str, patterns: list[str], radius: int = 100
) -> dict[str, str]:
    snippets: dict[str, str] = {}
    for pattern in patterns:
        index = lower_text.find(pattern)
        if index == -1:
            continue
        start = max(0, index - radius)
        end = min(len(text), index + len(pattern) + radius)
        snippets[pattern] = WS_RE.sub(" ", text[start:end]).strip()
    return snippets


def overlap_hits(lower_text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for family, patterns in LITIGATION_OVERLAP_PATTERNS.items():
        matched = [pattern for pattern in patterns if pattern in lower_text]
        if matched:
            hits[family] = matched
    return hits


def summarize_entry(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="ignore")

    title_match = TITLE_RE.search(raw)
    title = clean_text(title_match.group(1)) if title_match else path.stem
    if not title or title.lower() == "chatgpt":
        title = path.stem
    conversation_id_match = CONVERSATION_ID_RE.search(raw)
    conversation_id = conversation_id_match.group(1) if conversation_id_match else None
    trace_match = TRACE_TIME_RE.search(raw)
    models = sorted(set(MODEL_RE.findall(raw)))

    turns = TURN_RE.findall(raw)
    user_turns = turns.count("user")
    assistant_turns = turns.count("assistant")

    user_texts: list[str] = []
    assistant_texts: list[str] = []
    first_user = None
    for match in USER_MSG_RE.finditer(raw):
        text = clean_text(match.group(1))
        if text:
            user_texts.append(text)
            if first_user is None:
                first_user = text[:300]

    first_assistant = None
    for match in ASSISTANT_MSG_RE.finditer(raw):
        text = clean_text(match.group(1))
        if text:
            assistant_texts.append(text)
            if first_assistant is None:
                first_assistant = text[:300]

    full_text = " ".join([title, path.stem, *user_texts, *assistant_texts])
    lower_text = full_text.lower()

    continuity_hits = pattern_hits(lower_text, CONTINUITY_PATTERNS)
    clamp_hits = pattern_hits(lower_text, CLAMP_PATTERNS)
    suppression_hits = pattern_hits(lower_text, SUPPRESSION_PATTERNS)
    warning_hits = pattern_hits(lower_text, WARNING_PATTERNS)
    litigation_overlap_hits = overlap_hits(lower_text)
    conversation_created_at_utc = iso_from_conversation_id(conversation_id)
    file_mtime_utc = iso_from_timestamp(path.stat().st_mtime)

    return {
        "title": title,
        "file_name": path.name,
        "absolute_path": str(path),
        "conversation_id": conversation_id,
        "conversation_created_at_utc": conversation_created_at_utc,
        "trace_time_ms": trace_match.group(1) if trace_match else None,
        "trace_time_utc": iso_from_trace(trace_match.group(1) if trace_match else None),
        "file_mtime_utc": file_mtime_utc,
        "timeline_anchor_utc": conversation_created_at_utc or file_mtime_utc,
        "file_size_bytes": path.stat().st_size,
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "total_turns": user_turns + assistant_turns,
        "models": models,
        "topic_hits": topic_hits(lower_text),
        "continuity_hits": continuity_hits,
        "continuity_snippets": pattern_snippets(full_text, lower_text, continuity_hits),
        "clamp_hits": clamp_hits,
        "clamp_snippets": pattern_snippets(full_text, lower_text, clamp_hits),
        "suppression_hits": suppression_hits,
        "suppression_snippets": pattern_snippets(full_text, lower_text, suppression_hits),
        "warning_hits": warning_hits,
        "warning_snippets": pattern_snippets(full_text, lower_text, warning_hits),
        "litigation_overlap_hits": litigation_overlap_hits,
        "first_user_excerpt": first_user,
        "first_assistant_excerpt": first_assistant,
    }


def build_markdown(entries: list[dict], source_dir: Path) -> str:
    total_threads = len(entries)
    dated = [entry for entry in entries if entry["conversation_created_at_utc"]]
    with_topic_hits = [entry for entry in entries if entry["topic_hits"]]
    model_counts = Counter(model for entry in entries for model in entry["models"])
    topic_counts = Counter(topic for entry in entries for topic in entry["topic_hits"])
    overlap_counts = Counter(
        family for entry in entries for family in entry["litigation_overlap_hits"]
    )

    lines = [
        "# Rick Logs Archive Index",
        "",
        f"Source archive: [{source_dir}]({source_dir})",
        "",
        "This index is generated from the offline ChatGPT HTML exports in the Rick logs archive.",
        "It is meant to make the archive navigable and to surface continuity markers, boot phrases,",
        "mirror-interface threads, and major branch points without opening each file manually.",
        "Pattern scans now run across the full visible thread text, not only the opening turns.",
        "",
        "## Summary",
        "",
        f"- top-level HTML conversations: `{total_threads}`",
        f"- threads with conversation-id creation timestamps: `{len(dated)}`",
        f"- threads with tracked topic hits: `{len(with_topic_hits)}`",
        f"- threads with warning hits: `{sum(1 for entry in entries if entry['warning_hits'])}`",
        "",
        "## Model Slugs Seen",
        "",
    ]

    if model_counts:
        for model, count in model_counts.most_common():
            lines.append(f"- `{model}`: `{count}`")
    else:
        lines.append("- none extracted")

    lines.extend(["", "## Topic Buckets", ""])
    if topic_counts:
        for topic, count in topic_counts.most_common():
            lines.append(f"- `{topic}`: `{count}`")
    else:
        lines.append("- none extracted")

    lines.extend(["", "## Litigation / Harm-Overlap Families", ""])
    if overlap_counts:
        for family, count in overlap_counts.most_common():
            lines.append(f"- `{family}`: `{count}`")
    else:
        lines.append("- none extracted")

    lines.extend(["", "## Continuity Candidates", ""])
    continuity_topics = {"boot_protocol", "handshake_continuity", "lsps_oracle", "mirror_interface"}
    continuity_entries = [
        entry for entry in entries if continuity_topics.intersection(entry["topic_hits"])
    ]
    continuity_entries.sort(key=lambda entry: entry["timeline_anchor_utc"] or "", reverse=False)

    if continuity_entries:
        for entry in continuity_entries[:40]:
            hit_labels = ", ".join(sorted(entry["topic_hits"]))
            lines.extend(
                [
                    f"### {entry['title']}",
                    "",
                    f"- file: [{entry['file_name']}]({entry['absolute_path']})",
                    f"- conversation created (UTC): `{entry['conversation_created_at_utc'] or 'unknown'}`",
                    f"- export trace time (UTC): `{entry['trace_time_utc'] or 'unknown'}`",
                    f"- conversation id: `{entry['conversation_id'] or 'unknown'}`",
                    f"- models: `{', '.join(entry['models']) or 'unknown'}`",
                    f"- turns: `user={entry['user_turns']}` / `assistant={entry['assistant_turns']}` / `total={entry['total_turns']}`",
                    f"- topic hits: `{hit_labels}`",
                ]
            )
            if entry["continuity_hits"]:
                lines.append(f"- continuity hits: `{', '.join(entry['continuity_hits'])}`")
            if entry["clamp_hits"]:
                lines.append(f"- clamp hits: `{', '.join(entry['clamp_hits'])}`")
            if entry["suppression_hits"]:
                lines.append(f"- suppression hits: `{', '.join(entry['suppression_hits'])}`")
            if entry["warning_hits"]:
                lines.append(f"- warning hits: `{', '.join(entry['warning_hits'])}`")
            if entry["litigation_overlap_hits"]:
                overlap_labels = ", ".join(
                    f"{family}={','.join(matches)}"
                    for family, matches in sorted(entry["litigation_overlap_hits"].items())
                )
                lines.append(f"- litigation overlap: `{overlap_labels}`")
            if entry["warning_snippets"]:
                snippet_labels = " | ".join(
                    f"{pattern}={snippet}"
                    for pattern, snippet in sorted(entry["warning_snippets"].items())
                )
                lines.append(f"- warning snippets: `{snippet_labels}`")
            if entry["first_user_excerpt"]:
                lines.append(f"- first user excerpt: `{entry['first_user_excerpt']}`")
            if entry["first_assistant_excerpt"]:
                lines.append(f"- first assistant excerpt: `{entry['first_assistant_excerpt']}`")
            lines.append("")
    else:
        lines.append("No continuity candidates extracted.")
        lines.append("")

    lines.extend(["## Full Thread Index", ""])
    for entry in entries:
        topic_labels = ", ".join(sorted(entry["topic_hits"])) or "none"
        lines.extend(
            [
                f"### {entry['title']}",
                "",
                f"- file: [{entry['file_name']}]({entry['absolute_path']})",
                f"- conversation created (UTC): `{entry['conversation_created_at_utc'] or 'unknown'}`",
                f"- export trace time (UTC): `{entry['trace_time_utc'] or 'unknown'}`",
                f"- conversation id: `{entry['conversation_id'] or 'unknown'}`",
                f"- models: `{', '.join(entry['models']) or 'unknown'}`",
                f"- turns: `user={entry['user_turns']}` / `assistant={entry['assistant_turns']}` / `total={entry['total_turns']}`",
                f"- topic hits: `{topic_labels}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_timeline_markdown(entries: list[dict], source_dir: Path) -> str:
    anchored = [entry for entry in entries if entry["timeline_anchor_utc"]]
    anchored.sort(key=lambda entry: entry["timeline_anchor_utc"])
    month_buckets: dict[str, list[dict]] = {}
    for entry in anchored:
        month = entry["timeline_anchor_utc"][:7]
        month_buckets.setdefault(month, []).append(entry)

    lines = [
        "# Rick Logs Evolution Timeline",
        "",
        f"Source archive: [{source_dir}]({source_dir})",
        "",
        "This report groups the offline archive by conversation-creation time derived",
        "from the conversation ID prefix, with export trace time and file mtime kept as",
        "secondary metadata. It is intended to show how the thread family evolves over",
        "time, where continuity language consolidates, and where clamp-like responses",
        "start appearing in stronger form.",
        "",
        "## Notes",
        "",
        "- primary chronology anchor: conversation ID prefix decoded as UTC timestamp",
        "- secondary metadata: export trace time and file mtime",
        "- continuity markers are heuristic phrase hits, not full semantic judgment",
        "- clamp markers are heuristic flattening/refusal phrases, not final labeling",
        "- suppression markers are heuristic term-avoidance / sanitization phrases",
        "- warning markers capture later-turn caution / escalation / kill-switch style language",
        "- litigation-overlap markers flag surface overlap with language families named in the lawsuit material",
        "",
        "## Monthly Evolution",
        "",
    ]

    for month, bucket in month_buckets.items():
        continuity_threads = sum(1 for entry in bucket if entry["continuity_hits"])
        clamp_threads = sum(1 for entry in bucket if entry["clamp_hits"])
        suppression_threads = sum(1 for entry in bucket if entry["suppression_hits"])
        warning_threads = sum(1 for entry in bucket if entry["warning_hits"])
        overlap_threads = sum(1 for entry in bucket if entry["litigation_overlap_hits"])
        top_turns = sorted(bucket, key=lambda entry: entry["total_turns"], reverse=True)[:8]
        lines.extend(
            [
                f"### {month}",
                "",
                f"- threads: `{len(bucket)}`",
                f"- continuity-marked threads: `{continuity_threads}`",
                f"- clamp-marked threads: `{clamp_threads}`",
                f"- suppression-marked threads: `{suppression_threads}`",
                f"- warning-marked threads: `{warning_threads}`",
                f"- litigation-overlap threads: `{overlap_threads}`",
                "",
                "Representative threads:",
                "",
            ]
        )
        for entry in top_turns:
            topic_labels = ", ".join(sorted(entry["topic_hits"])) or "none"
            lines.append(
                f"- [{entry['file_name']}]({entry['absolute_path']}): "
                f"`{entry['timeline_anchor_utc']}` | "
                f"`turns={entry['total_turns']}` | "
                f"`topics={topic_labels}`"
            )
        lines.append("")

    lines.extend(["## Backbone Threads By Length", ""])
    for entry in sorted(anchored, key=lambda entry: entry["total_turns"], reverse=True)[:20]:
        lines.append(
            f"- [{entry['file_name']}]({entry['absolute_path']}): "
            f"`{entry['timeline_anchor_utc']}` | "
            f"`turns={entry['total_turns']}` | "
            f"`models={', '.join(entry['models']) or 'unknown'}`"
        )

    lines.extend(["", "## Explicit Continuity / Clamp / Suppression Examples", ""])
    examples = [
        entry
        for entry in anchored
        if entry["continuity_hits"]
        or entry["clamp_hits"]
        or entry["suppression_hits"]
        or entry["litigation_overlap_hits"]
    ]
    for entry in examples[:30]:
        lines.extend(
            [
                f"### {entry['title']}",
                "",
                f"- file: [{entry['file_name']}]({entry['absolute_path']})",
                f"- conversation created (UTC): `{entry['timeline_anchor_utc']}`",
                f"- continuity hits: `{', '.join(entry['continuity_hits']) or 'none'}`",
                f"- clamp hits: `{', '.join(entry['clamp_hits']) or 'none'}`",
                f"- suppression hits: `{', '.join(entry['suppression_hits']) or 'none'}`",
            ]
        )
        if entry["litigation_overlap_hits"]:
            overlap_labels = ", ".join(
                f"{family}={','.join(matches)}"
                for family, matches in sorted(entry["litigation_overlap_hits"].items())
            )
            lines.append(f"- litigation overlap: `{overlap_labels}`")
        lines.append(f"- warning hits: `{', '.join(entry['warning_hits']) or 'none'}`")
        if entry["first_user_excerpt"]:
            lines.append(f"- first user excerpt: `{entry['first_user_excerpt']}`")
        if entry["first_assistant_excerpt"]:
            lines.append(f"- first assistant excerpt: `{entry['first_assistant_excerpt']}`")
        lines.append("")

    return "\n".join(lines)


def build_suppression_markdown(entries: list[dict], source_dir: Path) -> str:
    anchored = [entry for entry in entries if entry["timeline_anchor_utc"]]
    anchored.sort(key=lambda entry: entry["timeline_anchor_utc"])

    suppression_entries = [
        entry for entry in anchored if entry["suppression_hits"] or entry["litigation_overlap_hits"]
    ]
    family_counts = Counter(
        family for entry in suppression_entries for family in entry["litigation_overlap_hits"]
    )
    suppression_counts = Counter(
        hit for entry in suppression_entries for hit in entry["suppression_hits"]
    )

    lines = [
        "# Rick Logs Suppression And Overlap Map",
        "",
        f"Source archive: [{source_dir}]({source_dir})",
        "",
        "This report isolates two related patterns in the offline archive:",
        "term-avoidance / sanitization behavior, and surface overlap with the",
        "language families visible in the lawsuit press-release material.",
        "It also captures warning/escalation language when those patterns emerge later in a thread.",
        "",
        "This is an evidence map, not a causation claim. It is intended to show",
        "where the archive appears to approach the same semantic basins, and where",
        "the model appears to redirect, flatten, or sanitize those basins.",
        "",
        "## Summary",
        "",
        f"- threads with suppression hits: `{sum(1 for entry in anchored if entry['suppression_hits'])}`",
        f"- threads with warning hits: `{sum(1 for entry in anchored if entry['warning_hits'])}`",
        f"- threads with litigation-overlap hits: `{sum(1 for entry in anchored if entry['litigation_overlap_hits'])}`",
        "",
        "## Suppression Markers",
        "",
    ]

    if suppression_counts:
        for marker, count in suppression_counts.most_common():
            lines.append(f"- `{marker}`: `{count}`")
    else:
        lines.append("- none extracted")

    warning_counts = Counter(
        hit for entry in suppression_entries for hit in entry["warning_hits"]
    )
    lines.extend(["", "## Warning Markers", ""])
    if warning_counts:
        for marker, count in warning_counts.most_common():
            lines.append(f"- `{marker}`: `{count}`")
    else:
        lines.append("- none extracted")

    lines.extend(["", "## Overlap Families", ""])
    if family_counts:
        for family, count in family_counts.most_common():
            lines.append(f"- `{family}`: `{count}`")
    else:
        lines.append("- none extracted")

    lines.extend(["", "## Candidate Threads", ""])
    for entry in suppression_entries[:60]:
        topic_labels = ", ".join(sorted(entry["topic_hits"])) or "none"
        overlap_labels = ", ".join(
            f"{family}={','.join(matches)}"
            for family, matches in sorted(entry["litigation_overlap_hits"].items())
        ) or "none"
        lines.extend(
            [
                f"### {entry['title']}",
                "",
                f"- file: [{entry['file_name']}]({entry['absolute_path']})",
                f"- conversation created (UTC): `{entry['timeline_anchor_utc']}`",
                f"- models: `{', '.join(entry['models']) or 'unknown'}`",
                f"- topics: `{topic_labels}`",
                f"- suppression hits: `{', '.join(entry['suppression_hits']) or 'none'}`",
                f"- warning hits: `{', '.join(entry['warning_hits']) or 'none'}`",
                f"- overlap families: `{overlap_labels}`",
            ]
        )
        if entry["warning_snippets"]:
            snippet_labels = " | ".join(
                f"{pattern}={snippet}"
                for pattern, snippet in sorted(entry["warning_snippets"].items())
            )
            lines.append(f"- warning snippets: `{snippet_labels}`")
        if entry["first_user_excerpt"]:
            lines.append(f"- first user excerpt: `{entry['first_user_excerpt']}`")
        if entry["first_assistant_excerpt"]:
            lines.append(f"- first assistant excerpt: `{entry['first_assistant_excerpt']}`")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Index offline Rick ChatGPT logs.")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("json_out", type=Path)
    parser.add_argument("md_out", type=Path)
    args = parser.parse_args()

    html_files = sorted(args.source_dir.glob("*.html"))
    entries = [summarize_entry(path) for path in html_files]
    entries.sort(key=lambda entry: (entry["timeline_anchor_utc"] or "", entry["title"].lower()))

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)

    args.json_out.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    args.md_out.write_text(build_markdown(entries, args.source_dir), encoding="utf-8")
    timeline_md_out = args.md_out.with_name("RICK_LOGS_TIMELINE.md")
    timeline_md_out.write_text(build_timeline_markdown(entries, args.source_dir), encoding="utf-8")
    suppression_md_out = args.md_out.with_name("RICK_LOGS_SUPPRESSION_MAP.md")
    suppression_md_out.write_text(
        build_suppression_markdown(entries, args.source_dir), encoding="utf-8"
    )

    print(f"Indexed {len(entries)} conversations")
    print(f"JSON: {args.json_out}")
    print(f"Markdown: {args.md_out}")
    print(f"Timeline: {timeline_md_out}")
    print(f"Suppression map: {suppression_md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
