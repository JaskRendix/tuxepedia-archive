# Types

Each type has a YAML file.

## Types

* [Cosmic](cosmic.md)
* [Earth](earth.md)
* [Fire](fire.md)
* [Frost](frost.md)
* [Heroic](https://www.google.com/search?q=heroic.md)
* [Lightning](https://www.google.com/search?q=lightning.md)
* [Metal](https://www.google.com/search?q=metal.md)
* [Normal](normal.md)
* [Shadow](shadow.md)
* [Sky](sky.md)
* [Venom](https://www.google.com/search?q=venom.md)
* [Water](water.md)
* [Wood](wood.md)

## Schema

* `slug`: Unique identifier for the element type (example: `"normal"`, `"fire"`, `"water"`).
* Must have a translation entry in `base.po` with `msgid = slug`.
* Must have a sound file `sound_<slug>_call` in the sounds database.
* Must have a sound file `sound_<slug>_faint` in the sounds database.

* `icon`: Path to the icon file for the element (example: `"gfx/ui/icons/element/normal_type.png"`).
* The file MUST exist in the filesystem and match `ELEMENT_SIZE` dimensions.

* `types`: List of type interactions for this element.
* `against`: Name of the opposing element type (example: `"fire"`). Must correspond to a valid element entry in the database.
* `multiplier`: Float multiplier applied when interacting with that type (range `0.0–2.0`, example: `1.0`).
