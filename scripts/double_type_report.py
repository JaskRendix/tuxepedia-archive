#!/usr/bin/env python3

from itertools import combinations
from pathlib import Path
import statistics
import sys

import yaml


TYPES_DIR = Path(__file__).resolve().parent.parent / "types"


def load_type(path):
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")

    slug = data.get("slug") or path.stem

    raw_types = data.get("types")

    if not isinstance(raw_types, list):
        raise ValueError(f"{path}: invalid 'types' section")

    matchups = {}

    for entry in raw_types:
        target = str(entry["against"])
        multiplier = float(entry["multiplier"])
        matchups[target] = multiplier

    return {
        "slug": slug,
        "matchups": matchups,
    }


def load_records():
    paths = sorted(TYPES_DIR.glob("*.yaml"))

    if not paths:
        sys.exit(f"No YAML files found in {TYPES_DIR}")

    return [load_type(path) for path in paths]


def dual_types(records):
    slugs = sorted(r["slug"] for r in records)

    return list(combinations(slugs, 2))


def incoming_profile(by_slug, dual_type):
    a, b = dual_type

    profile = {}

    for attacker in by_slug:
        profile[attacker] = (
            by_slug[attacker]["matchups"][a]
            * by_slug[attacker]["matchups"][b]
        )

    return profile


def analyze_dual_defense(records):
    by_slug = {r["slug"]: r for r in records}

    results = []

    for dual in dual_types(records):
        profile = incoming_profile(by_slug, dual)

        profile_values = [
            mult
            for attacker, mult in profile.items()
            if attacker not in dual
        ]

        avg_taken = statistics.mean(profile_values)

        weaknesses_2x = [
            attacker
            for attacker, mult in profile.items()
            if mult >= 2
        ]

        weaknesses_4x = [
            attacker
            for attacker, mult in profile.items()
            if mult >= 4
        ]

        resistances_half = [
            attacker
            for attacker, mult in profile.items()
            if mult <= 0.5
        ]

        resistances_quarter = [
            attacker
            for attacker, mult in profile.items()
            if mult <= 0.25
        ]
        
        results.append(
            {
                "types": dual,
                "avg_taken": avg_taken,
                "stdev_taken": statistics.pstdev(profile_values),
                "max_damage": max(profile.values()),
                "min_damage": min(profile.values()),
                "weaknesses_2x": weaknesses_2x,
                "weaknesses_4x": weaknesses_4x,
                "resistances_half": resistances_half,
                "resistances_quarter": resistances_quarter,
                "profile": profile,
            }
        )

    return results


def analyze_dual_offense(records):
    by_slug = {r["slug"]: r for r in records}

    results = []

    for t1, t2 in dual_types(records):

        coverage = []

        for defender in by_slug:

            best = max(
                by_slug[t1]["matchups"][defender],
                by_slug[t2]["matchups"][defender],
            )

            coverage.append(best)

        avg_offense = statistics.mean(coverage)

        super_hits = sum(
            1
            for m in coverage
            if m > 1
        )

        resisted_hits = sum(
            1
            for m in coverage
            if m < 1
        )

        results.append(
            {
                "types": (t1, t2),
                "avg_offense": avg_offense,
                "super_hits": super_hits,
                "resisted_hits": resisted_hits,
            }
        )

    return results


def format_dual(pair):
    return f"{pair[0]}/{pair[1]}"


def main():
    records = load_records()

    defensive = analyze_dual_defense(records)
    offensive = analyze_dual_offense(records)

    print("# Dual-Type Balance Report\n")

    print(
        f"Dual combinations analyzed: "
        f"**{len(defensive)}**\n"
    )

    strongest_defense = sorted(
        defensive,
        key=lambda x: (
            x["avg_taken"],
            x["stdev_taken"],
            len(x["weaknesses_4x"]),
        ),
    )[:10]

    weakest_defense = sorted(
        defensive,
        key=lambda x: (
            -x["avg_taken"],
            -x["stdev_taken"],
            -len(x["weaknesses_4x"]),
        ),
    )[:10]

    print("## Strongest Defensive Dual Types\n")

    for result in strongest_defense:
        print(
            f"- **{format_dual(result['types'])}** "
            f"(avg damage taken: {result['avg_taken']:.2f}, "
            f"stdev: {result['stdev_taken']:.2f}, "
            f"4x weaknesses: {len(result['weaknesses_4x'])}, "
            f"0.25x resistances: {len(result['resistances_quarter'])})"
        )

    print("\n## Weakest Defensive Dual Types\n")

    for result in weakest_defense:
        print(
            f"- **{format_dual(result['types'])}** "
            f"(avg damage taken: {result['avg_taken']:.2f}, "
            f"stdev: {result['stdev_taken']:.2f}, "
            f"4x weaknesses: {len(result['weaknesses_4x'])}, "
            f"0.25x resistances: {len(result['resistances_quarter'])})"
        )

    print("\n## Extreme Weaknesses (4x)\n")

    found = False

    for result in sorted(
        defensive,
        key=lambda r: format_dual(r["types"])
    ):
        if result["weaknesses_4x"]:
            found = True

            print(
                f"- **{format_dual(result['types'])}** "
                f"weak to "
                f"{', '.join(sorted(result['weaknesses_4x']))}"
            )

    if not found:
        print("No 4x weaknesses found.")

    print("\n## Extreme Resistances (0.25x)\n")

    found = False

    for result in sorted(
        defensive,
        key=lambda r: format_dual(r["types"])
    ):
        if result["resistances_quarter"]:
            found = True

            print(
                f"- **{format_dual(result['types'])}** "
                f"resists "
                f"{', '.join(sorted(result['resistances_quarter']))}"
            )

    if not found:
        print("No 0.25x resistances found.")

    most_polarized = sorted(
        defensive,
        key=lambda r: (
            -r["stdev_taken"],
            -abs(r["avg_taken"] - 1.0),
            -len(r["weaknesses_4x"]),
            -len(r["resistances_quarter"]),
        ),
    )[:10]
    
    print("\n## Most Polarized Dual Types\n")

    for result in most_polarized:
        print(
            f"- **{format_dual(result['types'])}** "
            f"(avg: {result['avg_taken']:.2f}, "
            f"stdev: {result['stdev_taken']:.2f}, "
            f"4x weaknesses: {len(result['weaknesses_4x'])}, "
            f"0.25x resistances: {len(result['resistances_quarter'])})"
        )

    most_stable = sorted(
        defensive,
        key=lambda r: (
            r["stdev_taken"],
            abs(r["avg_taken"] - 1.0),
        ),
    )[:10]

    print("\n## Most Stable Dual Types\n")

    for result in most_stable:
        print(
            f"- **{format_dual(result['types'])}** "
            f"(avg: {result['avg_taken']:.2f}, "
            f"stdev: {result['stdev_taken']:.2f})"
        )

    best_offense = sorted(
        offensive,
        key=lambda r: (
            -r["avg_offense"],
            -r["super_hits"],
        ),
    )[:10]

    print("\n## Best Offensive Dual Types\n")

    for result in best_offense:
        print(
            f"- **{format_dual(result['types'])}** "
            f"(avg offense: "
            f"{result['avg_offense']:.2f}, "
            f"super-effective targets: "
            f"{result['super_hits']}, "
            f"resisted targets: "
            f"{result['resisted_hits']})"
        )


if __name__ == "__main__":
    main()
