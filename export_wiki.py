import hashlib
import json
import os
import re

import mwclient  # type: ignore[import-untyped]
import requests

WIKI_HOST = "wiki.tuxemon.org"

USER_AGENT = (
    "TuxepediaArchiver/1.0 " "(https://github.com/your-username/tuxepedia-archive)"
)


def safe_filename(name):
    """Make page titles safe as filenames."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip(". ")
    return name[:240]


def sha1_file(path):
    """Compute SHA-1 hash of a file."""
    h = hashlib.sha1()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


print("Connecting to Tuxepedia...")

site = mwclient.Site(
    WIKI_HOST,
    path="/",
    clients_useragent=USER_AGENT,
)

print(f"Connected to {site.site['sitename']}")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

os.makedirs("pages", exist_ok=True)
os.makedirs("images", exist_ok=True)

#
# Export pages
#
print("\nExporting pages...")

for ns_id, ns_data in site.namespaces.items():

    if ns_id < 0:
        continue

    if isinstance(ns_data, dict):
        ns_name = ns_data.get("*", "")
    else:
        ns_name = str(ns_data)

    folder_name = ns_name or "Main"

    out_dir = os.path.join(
        "pages",
        safe_filename(folder_name),
    )

    os.makedirs(out_dir, exist_ok=True)

    print(f"\nNamespace: {folder_name}")

    for page in site.allpages(namespace=ns_id):

        title = page.name

        if ":" in title and ns_id != 0:
            short_title = title.split(":", 1)[1]
        else:
            short_title = title

        base_name = safe_filename(short_title)

        text_path = os.path.join(
            out_dir,
            f"{base_name}.mediawiki",
        )

        meta_path = os.path.join(
            out_dir,
            f"{base_name}.json",
        )

        if os.path.exists(text_path) and os.path.exists(meta_path):
            continue

        try:
            text = page.text()

            with open(text_path, "w", encoding="utf-8") as text_file:
                text_file.write(text)

            metadata = {
                "title": title,
            }

            try:
                metadata["pageid"] = page.pageid
            except Exception:
                pass

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    metadata,
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            print(f"  Saved: {title}")

        except Exception as e:
            print(f"  ERROR page {title}: {e}")

#
# Export images
#
print("\nExporting images...")

for image in site.allimages():

    try:
        image_name = image.name.split(":", 1)[1]

        filename = safe_filename(image_name)

        filepath = os.path.join(
            "images",
            filename,
        )

        # Skip images already downloaded
        if os.path.exists(filepath):
            continue

        #
        # Get image info through API
        #
        info = image.imageinfo

        if isinstance(info, list):
            info = info[0]

        url = info.get("url")

        if not url:
            print(f"  Skipping image without URL: {image.name}")
            continue

        response = session.get(
            url,
            stream=True,
            timeout=60,
        )

        response.raise_for_status()

        tmpfile = filepath + ".tmp"

        with open(tmpfile, "wb") as binary_file:
            for chunk in response.iter_content(65536):
                if chunk:
                    binary_file.write(chunk)

        if os.path.exists(filepath):

            old_hash = sha1_file(filepath)
            new_hash = sha1_file(tmpfile)

            if old_hash == new_hash:
                os.remove(tmpfile)
                continue

        os.replace(tmpfile, filepath)

        print(f"  Downloaded: {filename}")

    except Exception as e:
        print(f"  ERROR image {image.name}: {e}")

print("\nDone.")
