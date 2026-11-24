#!/usr/bin/env python3

from pathlib import Path
import sys

import yaml

SHAPES_DIR = Path(__file__).resolve().parent.parent / "shapes"
ATTRIBUTES = ("speed", "hp", "melee", "ranged", "armour", "dodge")


def load_shape(path):
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    # Also accept a one-item list, like the entries in the combined YAML.
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
        raise ValueError(f"{path}: missing attributes: {', '.join(sorted(missing))}")

    for name in ATTRIBUTES:
        if not isinstance(attributes[name], int) or isinstance(attributes[name], bool):
            raise ValueError(f"{path}: '{name}' must be an integer")

    return slug, attributes


def main():
    paths = sorted(
        path for path in SHAPES_DIR.glob("*.yaml")
        if path.name != "shapes.yaml"
    )

    if not paths:
        sys.exit(f"No individual YAML files found in {SHAPES_DIR}")

    shapes = [load_shape(path) for path in paths]

    print("# Shape Balance Report\n")
    print(f"Shapes analyzed: **{len(shapes)}**\n")

    print("## Attribute Summary\n")
    print("| Attribute | Min | Average | Max |")
    print("|---|---:|---:|---:|")

    for attribute in ATTRIBUTES:
        values = [stats[attribute] for _, stats in shapes]
        print(
            f"| {attribute.title()} | {min(values)} "
            f"| {sum(values) / len(values):.2f} | {max(values)} |"
        )

    print("\n## Shape Stat Totals\n")
    print("| Shape | Total |")
    print("|---|---:|")

    for slug, stats in sorted(
        shapes,
        key=lambda shape: sum(shape[1][attribute] for attribute in ATTRIBUTES),
        reverse=True,
    ):
        total = sum(stats[attribute] for attribute in ATTRIBUTES)
        print(f"| {slug} | {total} |")


if __name__ == "__main__":
    main()
