"""Build a local, read-only Music Production registry from the environment audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from bible_paths import material
AUDIT = material("environment_audit.json")
OUT = material("audio", "plugin_registry.json")

GUIDES = {
    "Steinberg Cubase 13": ("daw", "DAW project, MIDI, routing and automation", "https://www.steinberg.help/"),
    "Steinberg Cubase 15": ("daw", "DAW project, MIDI, routing and automation", "https://www.steinberg.help/"),
    "Steinberg Nuendo 12": ("daw", "DAW and post-production workflow", "https://www.steinberg.help/"),
    "REAPER (x64)": ("daw", "DAW, routing, actions and scripting", "https://www.reaper.fm/userguide.php"),
    "FabFilter Total Bundle": ("mixing", "EQ, compression, saturation and limiting", "https://www.fabfilter.com/help"),
    "FabFilter Pro-Q 2": ("mixing", "Parametric EQ and spectrum analysis", "https://www.fabfilter.com/help/pro-q"),
    "iZotope Ozone 9": ("mastering", "Mastering chain and loudness tools", "https://www.izotope.com/en/products/ozone.html"),
    "iZotope Nectar 3": ("voice", "Vocal editing and processing chain", "https://www.izotope.com/en/products/nectar.html"),
    "Native Instruments Guitar Rig 5": ("guitar", "Amp, cabinet and effects chain", "https://www.native-instruments.com/en/products/komplete/guitar/guitar-rig-5-player/"),
    "Native Instruments Guitar Rig 6": ("guitar", "Amp, cabinet and effects chain", "https://www.native-instruments.com/en/products/komplete/guitar/guitar-rig-6-player/"),
    "IK Multimedia MODO BASS 2": ("instrument", "Physical-modelled bass instrument", "https://www.ikmultimedia.com/products/modobass2/"),
    "EZdrummer 3 by Team V.R": ("instrument", "Drum instrument, MIDI and groove workflow", "https://www.toontrack.com/product/ezdrummer-3/"),
    "Native Instruments Kontakt 7": ("instrument", "Sample instrument host", "https://www.native-instruments.com/en/catalog/software/kontakt/"),
    "Native Instruments Kontakt 8": ("instrument", "Sample instrument host", "https://www.native-instruments.com/en/catalog/software/kontakt/"),
    "XLN Audio Addictive Keys": ("instrument", "Virtual keyboard instrument", "https://www.xlnaudio.com/products/addictive_keys"),
}


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    installed = audit.get("installed_programs", [])
    products = []
    for row in installed:
        name = str(row.get("name", ""))
        if name not in GUIDES:
            continue
        category, function, docs = GUIDES[name]
        products.append({
            "name": name,
            "version": str(row.get("version", "")),
            "publisher": row.get("publisher", ""),
            "install_location": row.get("install_location", ""),
            "category": category,
            "function": function,
            "documentation": docs,
            "availability": "installed_by_environment_audit",
            "loaded_in_daw": "not_tested",
            "source": "data/Bible/.internal/sources/knowledge3/environment_audit.json",
        })
    paths = audit.get("paths", {})
    registry = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "products": sorted(products, key=lambda item: item["name"].lower()),
        "plugin_paths": {
            "vst2": paths.get("vst2", {}).get("paths", []),
            "vst3": paths.get("vst3", {}).get("paths", []),
        },
        "limitations": [
            "Наличие файла или записи установки не подтверждает загрузку плагина в DAW.",
            "Лицензии и совместимость не проверяются этим read-only реестром.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"products": len(products), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
