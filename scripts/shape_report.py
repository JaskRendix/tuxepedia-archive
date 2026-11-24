#!/usr/bin/env python3

from collections import Counter, defaultdict
from pathlib import Path
import statistics
import sys

import yaml


SHAPES_DIR = Path(__file__).resolve().parent.parent / "shapes"

ATTRIBUTES = (
    "speed",
    "hp",
    "melee",
    "ranged",
    "armour",
    "dodge",
)


def load_shape(path):
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    # Also accept a one-item list, like entries in the combined YAML.
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError(f"{path}: expected a single shape entry")
        data = data[0]

    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")

    slug = data.get("slug", path.stem)
    attributes = data.get("attributes")

    if not isinstance(attributes, dict):
        raise ValueError(f"{path}: missing or invalid 'attributes' mapping")

    missing = set(ATTRIBUTES) - attributes.keys()
    if missing:
        raise ValueError(
            f"{path}: missing attributes: {', '.join(sorted(missing))}"
        )

    for name in ATTRIBUTES:
        if (
            not isinstance(attributes[name], int)
            or isinstance(attributes[name], bool)
        ):
            raise ValueError(f"{path}: '{name}' must be an integer")

    return slug, attributes


def classify_archetype(stats):
    hp_armour = stats["hp"] + stats["armour"]
    speed_dodge = stats["speed"] + stats["dodge"]

    tags = []

    if hp_armour >= 16:
        tags.append("Tank")

    if speed_dodge >= 16:
        tags.append("Skirmisher")

    if stats["ranged"] >= 8:
        tags.append("Shooter")

    if stats["melee"] >= 8:
        tags.append("Bruiser")

    if not tags:
        max_val = max(stats[attr] for attr in ATTRIBUTES)
        min_val = min(stats[attr] for attr in ATTRIBUTES)

        if max_val - min_val <= 1:
            return "Balanced"

        return "Hybrid"

    return " / ".join(tags)


def build_shape_records(shapes):
    records = []

    for slug, stats in shapes:
        values = [stats[attr] for attr in ATTRIBUTES]

        total = sum(values)
        stat_range = max(values) - min(values)
        stddev = statistics.pstdev(values)

        max_value = max(values)
        top_attributes = [
            attr
            for attr in ATTRIBUTES
            if stats[attr] == max_value
        ]

        records.append(
            {
                "slug": slug,
                "stats": stats,
                "values": values,
                "fingerprint": tuple(values),
                "total": total,
                "range": stat_range,
                "stddev": stddev,
                "archetype": classify_archetype(stats),
                "top_attributes": top_attributes,
            }
        )

    return records


def dominates(a, b):
    return (
        all(a[attr] >= b[attr] for attr in ATTRIBUTES)
        and any(a[attr] > b[attr] for attr in ATTRIBUTES)
    )


def find_dominated_shapes(records):
    dominated = []

    for target in records:
        dominators = [
            candidate["slug"]
            for candidate in records
            if candidate["slug"] != target["slug"]
            and dominates(candidate["stats"], target["stats"])
        ]

        if dominators:
            dominated.append((target["slug"], sorted(dominators)))

    return dominated


def find_pareto_frontier(records):
    frontier = []

    for record in records:
        is_dominated = any(
            other["slug"] != record["slug"]
            and dominates(other["stats"], record["stats"])
            for other in records
        )

        if not is_dominated:
            frontier.append(record["slug"])

    return sorted(frontier)


def find_duplicate_statlines(records):
    by_fingerprint = defaultdict(list)

    for record in records:
        by_fingerprint[record["fingerprint"]].append(record["slug"])

    return [
        sorted(slugs)
        for slugs in by_fingerprint.values()
        if len(slugs) > 1
    ]


def archetype_counts(records):
    counter = Counter()

    for record in records:
        counter[record["archetype"]] += 1

    return counter


def format_extreme_holders(records, attr, pick_max):
    values = [record["stats"][attr] for record in records]

    target_value = max(values) if pick_max else min(values)

    holders = [
        record["slug"]
        for record in records
        if record["stats"][attr] == target_value
    ]

    return f"{', '.join(sorted(holders))} ({target_value})"


def main():
    paths = sorted(
        path
        for path in SHAPES_DIR.glob("*.yaml")
        if path.name != "shapes.yaml"
    )

    if not paths:
        sys.exit(
            f"No individual YAML files found in {SHAPES_DIR}"
        )

    shapes = [load_shape(path) for path in paths]
    records = build_shape_records(shapes)

    common_total = Counter(
        record["total"] for record in records
    ).most_common(1)[0][0]

    distinct_totals = sorted(
        {record["total"] for record in records}
    )

    print("# Shape Balance Report\n")

    print(f"Shapes analyzed: **{len(records)}**\n")

    if len(distinct_totals) == 1:
        print(
            f"All shapes share the same stat total: "
            f"**{common_total}**.\n"
        )
    else:
        totals = ", ".join(str(t) for t in distinct_totals)
        print(
            f"Stat totals vary across shapes ({totals}); "
            f"most common total is **{common_total}**.\n"
        )

    print("## Attribute Summary\n")

    print("| Attribute | Min | Median | Average | Max |")
    print("|---|---:|---:|---:|---:|")

    for attribute in ATTRIBUTES:
        values = [
            record["stats"][attribute]
            for record in records
        ]

        print(
            f"| {attribute.title()} "
            f"| {min(values)} "
            f"| {statistics.median(values):.2f} "
            f"| {statistics.mean(values):.2f} "
            f"| {max(values)} |"
        )

    header_cols = (
        ["Shape", "Archetype"]
        + [attr.title() for attr in ATTRIBUTES]
        + ["Total", "Range", "StdDev"]
    )

    align_row = "|---|---|" + "---:|" * (
        len(ATTRIBUTES) + 3
    )

    print("\n## Per-Shape Breakdown\n")

    print("| " + " | ".join(header_cols) + " |")
    print(align_row)

    ranked_records = sorted(
        records,
        key=lambda record: (
            -record["total"],
            record["slug"],
        ),
    )

    for record in ranked_records:
        row = (
            [record["slug"], record["archetype"]]
            + [str(v) for v in record["values"]]
            + [
                str(record["total"]),
                str(record["range"]),
                f"{record['stddev']:.2f}",
            ]
        )

        print("| " + " | ".join(row) + " |")

    print("\n## Extreme Values\n")

    for attribute in ATTRIBUTES:
        highest = format_extreme_holders(
            records,
            attribute,
            pick_max=True,
        )

        lowest = format_extreme_holders(
            records,
            attribute,
            pick_max=False,
        )

        print(
            f"- **{attribute.title()}** "
            f"— Highest: {highest} | Lowest: {lowest}"
        )

    print("\n## Signature Strengths\n")

    for record in sorted(records, key=lambda r: r["slug"]):
        strengths = ", ".join(
            attr.title()
            for attr in record["top_attributes"]
        )

        print(
            f"- **{record['slug']}**: {strengths}"
        )

    dominated = find_dominated_shapes(records)

    print("\n## Dominance Analysis\n")

    if dominated:
        for slug, dominators in dominated:
            print(
                f"- **{slug}** is dominated by "
                f"{', '.join(dominators)}"
            )
    else:
        print("No dominated shapes found.")

    frontier = find_pareto_frontier(records)

    print("\n## Pareto Frontier\n")

    for slug in frontier:
        print(f"- {slug}")

    duplicates = find_duplicate_statlines(records)

    print("\n## Duplicate Statlines\n")

    if duplicates:
        for group in duplicates:
            print(
                f"- Identical stats: "
                f"{', '.join(group)}"
            )
    else:
        print("No duplicate statlines found.")

    print("\n## Archetype Distribution\n")

    archetypes = archetype_counts(records)

    for archetype, count in sorted(
        archetypes.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"- {archetype}: {count}")


if __name__ == "__main__":
    main()
