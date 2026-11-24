# Shapes

Each shape has a YAML file containing its data and a Markdown file with its documentation.

- `slug`: Unique identifier for the shape (example: `blob`, `dragon`, `knight`). A translation entry with this `msgid` must exist in `base.po`, otherwise validation fails.
- `attributes`: Statistical attributes of the shape:
  - `armour`: Integer armour value (example: `8`)
  - `dodge`: Integer dodge/avoidance value (example: `4`)
  - `hp`: Hit Points (health) value (example: `8`)
  - `melee`: Melee attack strength (example: `4`)
  - `ranged`: Ranged attack strength (example: `8`)
  - `speed`: Movement speed value (example: `4`)

## Shapes

- [Blob](blob.md)
- [Brute](brute.md)
- [Dragon](dragon.md)
- [Flier](flier.md)
- [Grub](grub.md)
- [Humanoid](humanoid.md)
- [Hunter](hunter.md)
- [Landrace](landrace.md)
- [Leviathan](leviathan.md)
- [Piscine](piscine.md)
- [Polliwog](polliwog.md)
- [Serpent](serpent.md)
- [Sprite](sprite.md)
- [Varmint](varmint.md)
