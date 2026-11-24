#!/usr/bin/env python3

import argparse
from pathlib import Path
import statistics
import sys

import yaml


TYPES_DIR = Path(__file__).resolve().parent.parent / "types"
EXPECTED_MULTIPLIERS = {0.5, 1, 2}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a Markdown balance report for elemental types."
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Include the full pairwise matchup matrix in the report.",
    )
    return parser.parse_args()


def load_type(path):
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")

    slug = data.get("slug") or path.stem
    raw_types = data.get("types")

    if not isinstance(raw_types, list) or not raw_types:
        raise ValueError(f"{path}: missing or invalid 'types' list")

    matchups = {}
    for entry in raw_types:
        if (
            not isinstance(entry, dict)
            or "against" not in entry
            or "multiplier" not in entry
        ):
            raise ValueError(f"{path}: invalid entry in 'types': {entry}")

        target = str(entry["against"])
        mult = entry["multiplier"]

        if isinstance(mult, bool) or not isinstance(mult, (int, float)):
            raise ValueError(f"{path}: multiplier for '{target}' must be numeric")

        if target in matchups:
            raise ValueError(f"{path}: duplicate matchup against '{target}'")

        matchups[target] = float(mult)

    return {
        "slug": slug,
        "matchups": matchups,
    }


def validate_chart(records):
    by_slug = {r["slug"]: r for r in records}
    all_slugs = sorted(by_slug.keys())
    issues = []

    for slug, record in sorted(by_slug.items()):
        targets = set(record["matchups"].keys())
        expected_targets = set(all_slugs)

        missing = sorted(expected_targets - targets)
        extra = sorted(targets - expected_targets)
        if missing:
            issues.append(
                f"**{slug}** missing matchups against: {', '.join(missing)}"
            )
        if extra:
            issues.append(
                f"**{slug}** has unknown targets: {', '.join(extra)}"
            )

        for target, mult in sorted(record["matchups"].items()):
            if mult not in EXPECTED_MULTIPLIERS:
                issues.append(
                    f"**{slug} -> {target}** uses non-standard multiplier `{mult:g}`"
                )

    return issues


def build_type_stats(records):
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())
    stats = {}

    for attacker in slugs:
        # Exclude self-matchups from aggregate balance metrics so own-type rules
        # do not dilute cross-type offensive/defensive comparisons.
        out_mults = [
            by_slug[attacker]["matchups"].get(defender, 1.0)
            for defender in slugs
            if defender != attacker
        ]
        in_mults = [
            by_slug[defender]["matchups"].get(attacker, 1.0)
            for defender in slugs
            if defender != attacker
        ]

        super_off = sum(1 for m in out_mults if m > 1.0)
        resisted_off = sum(1 for m in out_mults if m < 1.0)
        neutral_off = sum(1 for m in out_mults if m == 1.0)

        weak_def = sum(1 for m in in_mults if m > 1.0)
        resist_def = sum(1 for m in in_mults if m < 1.0)
        neutral_def = sum(1 for m in in_mults if m == 1.0)

        off_sum = sum(out_mults)
        def_sum = sum(in_mults)

        stats[attacker] = {
            "slug": attacker,
            "super_off": super_off,
            "neutral_off": neutral_off,
            "resisted_off": resisted_off,
            "off_sum": off_sum,
            "off_avg": statistics.mean(out_mults),
            "weak_def": weak_def,
            "neutral_def": neutral_def,
            "resist_def": resist_def,
            "def_sum": def_sum,
            "def_avg": statistics.mean(in_mults),
            "beats": super_off,
            "loses_to": weak_def,
            "net_advantage": (super_off - resisted_off)
            + (resist_def - weak_def),
        }

    return stats


def find_extreme_matchups(records):
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())
    per_type = {}

    for slug in slugs:
        off_pairs = [
            (defender, by_slug[slug]["matchups"].get(defender, 1.0))
            for defender in slugs
            if defender != slug
        ]
        def_pairs = [
            (attacker, by_slug[attacker]["matchups"].get(slug, 1.0))
            for attacker in slugs
            if attacker != slug
        ]

        max_off = max(m for _, m in off_pairs)
        min_off = min(m for _, m in off_pairs)
        max_def = max(m for _, m in def_pairs)
        min_def = min(m for _, m in def_pairs)

        per_type[slug] = {
            "strongest_off": [
                (t, m) for t, m in off_pairs if m == max_off and m > 1.0
            ],
            "weakest_off": [
                (t, m) for t, m in off_pairs if m == min_off and m < 1.0
            ],
            "biggest_threat_in": [
                (a, m) for a, m in def_pairs if m == max_def and m > 1.0
            ],
            "best_resist_in": [
                (a, m) for a, m in def_pairs if m == min_def and m < 1.0
            ],
        }

    return per_type


def find_top_defensive_counters(records, limit=3):
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())
    counters_by_target = {}

    for defender in slugs:
        candidates = []
        for attacker in slugs:
            if attacker == defender:
                continue

            to_defender = by_slug[attacker]["matchups"].get(defender, 1.0)
            from_defender = by_slug[defender]["matchups"].get(attacker, 1.0)

            if to_defender > 1.0 or from_defender < 1.0:
                # Positive values mean the attacker fares better in the duel.
                score = to_defender - from_defender
                candidates.append(
                    {
                        "attacker": attacker,
                        "to_defender": to_defender,
                        "from_defender": from_defender,
                        "score": score,
                    }
                )

        candidates.sort(
            key=lambda item: (
                -item["score"],
                -item["to_defender"],
                item["from_defender"],
                item["attacker"],
            )
        )
        counters_by_target[defender] = candidates[:limit]

    return counters_by_target


def find_asymmetries(records):
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())
    pairs = []

    for i, a in enumerate(slugs):
        for b in slugs[i + 1 :]:
            ab = by_slug[a]["matchups"].get(b, 1.0)
            ba = by_slug[b]["matchups"].get(a, 1.0)
            swing = abs(ab - ba)
            if swing > 0:
                pairs.append((swing, a, ab, b, ba))

    pairs.sort(key=lambda item: (-item[0], item[1], item[3]))
    return pairs


def find_reciprocity(records):
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())

    mutual_super = []
    mutual_resist = []
    one_way_super = []

    for i, a in enumerate(slugs):
        for b in slugs[i + 1 :]:
            ab = by_slug[a]["matchups"].get(b, 1.0)
            ba = by_slug[b]["matchups"].get(a, 1.0)

            if ab > 1.0 and ba > 1.0:
                mutual_super.append((a, ab, b, ba))
            elif ab < 1.0 and ba < 1.0:
                mutual_resist.append((a, ab, b, ba))

        for b in slugs:
            if a == b:
                continue
            ab = by_slug[a]["matchups"].get(b, 1.0)
            ba = by_slug[b]["matchups"].get(a, 1.0)
            if ab > 1.0 and ba <= 1.0:
                one_way_super.append((a, ab, b, ba))

    return mutual_super, mutual_resist, one_way_super


def _canonical_cycle_key(nodes):
    rotations = [nodes[i:] + nodes[:i] for i in range(len(nodes))]
    reversed_nodes = list(reversed(nodes))
    rev_rotations = [
        reversed_nodes[i:] + reversed_nodes[:i]
        for i in range(len(reversed_nodes))
    ]
    return min(tuple(c) for c in rotations + rev_rotations)


def find_three_cycles(records):
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())
    seen = set()
    cycles = []

    for a in slugs:
        for b in slugs:
            if b == a or by_slug[a]["matchups"].get(b, 1.0) <= 1.0:
                continue
            for c in slugs:
                if c in (a, b) or by_slug[b]["matchups"].get(c, 1.0) <= 1.0:
                    continue
                if by_slug[c]["matchups"].get(a, 1.0) > 1.0:
                    key = _canonical_cycle_key([a, b, c])
                    if key not in seen:
                        seen.add(key)
                        cycles.append((a, b, c))

    return cycles


def find_four_cycles(records):
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())
    seen = set()
    cycles = []

    for a in slugs:
        for b in slugs:
            if b == a or by_slug[a]["matchups"].get(b, 1.0) <= 1.0:
                continue
            for c in slugs:
                if c in (a, b) or by_slug[b]["matchups"].get(c, 1.0) <= 1.0:
                    continue
                for d in slugs:
                    if (
                        d in (a, b, c)
                        or by_slug[c]["matchups"].get(d, 1.0) <= 1.0
                    ):
                        continue
                    if by_slug[d]["matchups"].get(a, 1.0) > 1.0:
                        key = _canonical_cycle_key([a, b, c, d])
                        if key not in seen:
                            seen.add(key)
                            cycles.append((a, b, c, d))

    return cycles


def fmt_mult(val):
    return f"{val:g}x"


def fmt_targets(pairs):
    if not pairs:
        return "None"
    return ", ".join(f"{name} ({fmt_mult(mult)})" for name, mult in pairs)


def main():
    args = parse_args()
    paths = sorted(TYPES_DIR.glob("*.yaml"))
    if not paths:
        sys.exit(f"No YAML files found in {TYPES_DIR}")

    records = [load_type(path) for path in paths]
    by_slug = {r["slug"]: r for r in records}
    slugs = sorted(by_slug.keys())
    stats = build_type_stats(records)
    issues = validate_chart(records)

    print("# Type Balance Report\n")
    print(f"Types analyzed: **{len(records)}**\n")

    off_sums = [s["off_sum"] for s in stats.values()]
    def_sums = [s["def_sum"] for s in stats.values()]
    off_avgs = [s["off_avg"] for s in stats.values()]
    def_avgs = [s["def_avg"] for s in stats.values()]

    print(
        f"Offensive sum (excl. self) — Min: **{min(off_sums):g}**, "
        f"Avg: **{statistics.mean(off_sums):.2f}**, Max: **{max(off_sums):g}** "
        f"(per-type mean range: {min(off_avgs):.2f}–{max(off_avgs):.2f}).\n"
    )
    print(
        f"Incoming sum (excl. self) — Min: **{min(def_sums):g}**, "
        f"Avg: **{statistics.mean(def_sums):.2f}**, Max: **{max(def_sums):g}** "
        f"(per-type mean range: {min(def_avgs):.2f}–{max(def_avgs):.2f}).\n"
    )

    ranked = sorted(
        stats.values(),
        key=lambda s: (-s["net_advantage"], -s["off_avg"], s["slug"]),
    )

    print("## Ecosystem Position\n")
    beats_vals = [s["beats"] for s in ranked]
    loses_vals = [s["loses_to"] for s in ranked]
    print(
        f"Beats range: **{min(beats_vals)}–{max(beats_vals)}** "
        f"(avg {statistics.mean(beats_vals):.2f}) | "
        f"Loses to range: **{min(loses_vals)}–{max(loses_vals)}** "
        f"(avg {statistics.mean(loses_vals):.2f})\n"
    )
    for s in ranked:
        print(
            f"- **{s['slug'].title()}** — "
            f"Beats: **{s['beats']}** | Loses to: **{s['loses_to']}**"
        )

    print("\n## Offensive & Defensive Summary\n")
    print(
        "| Type | Off 2x | Off 1x | Off 0.5x | Off Sum | Off Avg "
        "| Def 2x | Def 1x | Def 0.5x | Def Sum | Def Avg | Net |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for s in ranked:
        print(
            f"| **{s['slug']}** "
            f"| {s['super_off']} | {s['neutral_off']} | {s['resisted_off']} "
            f"| {s['off_sum']:g} | {s['off_avg']:.2f} "
            f"| {s['weak_def']} | {s['neutral_def']} | {s['resist_def']} "
            f"| {s['def_sum']:g} | {s['def_avg']:.2f} "
            f"| {s['net_advantage']:+d} |"
        )

    extremes = find_extreme_matchups(records)
    print("\n## Strongest & Weakest Matchups\n")
    for slug in slugs:
        entry = extremes[slug]
        print(
            f"- **{slug}** — "
            f"Best Off: {fmt_targets(entry['strongest_off'])} | "
            f"Worst Off: {fmt_targets(entry['weakest_off'])} | "
            f"Weakest Def vs: {fmt_targets(entry['biggest_threat_in'])} | "
            f"Strongest Def vs: {fmt_targets(entry['best_resist_in'])}"
        )

    counters_by_target = find_top_defensive_counters(records)
    print("\n## Top Defensive Counters\n")
    for slug in slugs:
        counters = counters_by_target[slug]
        if counters:
            formatted = ", ".join(
                f"**{c['attacker']}** "
                f"(deals {fmt_mult(c['to_defender'])}, "
                f"takes {fmt_mult(c['from_defender'])}, "
                f"swing {c['score']:+g})"
                for c in counters
            )
            print(f"- **{slug}** — {formatted}")
        else:
            print(f"- **{slug}** — No favorable counters found")

    asymmetries = find_asymmetries(records)
    print("\n## Most Asymmetric Relationships\n")
    if asymmetries:
        for swing, a, ab, b, ba in asymmetries[:10]:
            print(
                f"- **{a} vs {b}** — Swing: **{swing:g}** "
                f"(`{a} -> {b}` = {fmt_mult(ab)}, `{b} -> {a}` = {fmt_mult(ba)})"
            )
    else:
        print("All pairwise matchups are symmetric.")

    three_cycles = find_three_cycles(records)
    print("\n## 3-Type Super-Effective Cycles\n")
    if three_cycles:
        for a, b, c in three_cycles:
            ab = by_slug[a]["matchups"].get(b, 1.0)
            bc = by_slug[b]["matchups"].get(c, 1.0)
            ca = by_slug[c]["matchups"].get(a, 1.0)
            print(
                f"- **{a}** ({fmt_mult(ab)}) -> **{b}** ({fmt_mult(bc)}) -> "
                f"**{c}** ({fmt_mult(ca)}) -> **{a}**"
            )
    else:
        print("No 3-type super-effective cycles found.")

    four_cycles = find_four_cycles(records)
    print("\n## 4-Type Super-Effective Cycles\n")
    if four_cycles:
        for a, b, c, d in four_cycles:
            ab = by_slug[a]["matchups"].get(b, 1.0)
            bc = by_slug[b]["matchups"].get(c, 1.0)
            cd = by_slug[c]["matchups"].get(d, 1.0)
            da = by_slug[d]["matchups"].get(a, 1.0)
            print(
                f"- **{a}** ({fmt_mult(ab)}) -> **{b}** ({fmt_mult(bc)}) -> "
                f"**{c}** ({fmt_mult(cd)}) -> **{d}** ({fmt_mult(da)}) -> **{a}**"
            )
    else:
        print("No 4-type super-effective cycles found.")

    if args.matrix:
        print("\n## Matchup Matrix (Row Attacks Column)\n")
        header = ["Attacker"] + [slug.title() for slug in slugs]
        print("| " + " | ".join(header) + " |")
        print("|---" + "|---:" * len(slugs) + "|")

        for attacker in slugs:
            cells = [f"**{attacker}**"]
            for defender in slugs:
                mult = by_slug[attacker]["matchups"].get(defender, 1.0)
                label = f"**{fmt_mult(mult)}**" if mult != 1.0 else fmt_mult(mult)
                cells.append(label)
            print("| " + " | ".join(cells) + " |")

    mutual_super, mutual_resist, one_way_super = find_reciprocity(records)

    print("\n## Reciprocity & Matchup Patterns\n")
    if mutual_super:
        pairs = ", ".join(
            f"{a} ({fmt_mult(ab)}) <-> {b} ({fmt_mult(ba)})"
            for a, ab, b, ba in mutual_super
        )
        print(f"- **Mutual Super Effective:** {pairs}")
    else:
        print("- **Mutual Super Effective:** None")

    if mutual_resist:
        pairs = ", ".join(
            f"{a} ({fmt_mult(ab)}) <-> {b} ({fmt_mult(ba)})"
            for a, ab, b, ba in mutual_resist
        )
        print(f"- **Mutual Resisted:** {pairs}")
    else:
        print("- **Mutual Resisted:** None")

    if one_way_super:
        pairs = ", ".join(
            f"{a} -> {b} ({fmt_mult(ab)}, return {fmt_mult(ba)})"
            for a, ab, b, ba in one_way_super
        )
        print(f"- **Unreciprocated Super Effective:** {pairs}")
    else:
        print("- **Unreciprocated Super Effective:** None")

    no_resisted_off = [s["slug"] for s in ranked if s["resisted_off"] == 0]
    print(
        f"- **No `0.5x` Offensive Matchups:** "
        f"{', '.join(no_resisted_off) if no_resisted_off else 'None'}"
    )

    no_super_effective = [s["slug"] for s in ranked if s["super_off"] == 0]
    print(
        f"- **Cannot hit anything super-effectively (`0x` `2x` matchups):** "
        f"{', '.join(no_super_effective) if no_super_effective else 'None'}"
    )

    print("\n## Validation & Anomalies\n")
    if issues:
        for issue in issues:
            print(f"- {issue}")
    else:
        print("No validation issues found.")


if __name__ == "__main__":
    main()
