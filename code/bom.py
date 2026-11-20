"""The bill of materials, counted from the built assemblies.

Runs under freecadcmd, one process for all; FCARGS names the top-level
assembly documents (`rebuild.py bom` passes every assembly that no other one
needs).  Writes BOM.md for people and data/bom.json for tools.

Counted, not listed: a list somebody keeps up to date does not stay true.
The walk starts at each top-level assembly and goes down through every
sub-assembly link, multiplying, so a part inside a sub-assembly linked four
times counts four times.  What each thing is comes from the documents
themselves, with the rule the assemblies' groups are made with
(`fcasm.category`):

- a printed part is named by its document, with its material;
- a fastener by what the Fasteners workbench made it from: its type,
  diameter and length (`ISO 4762`, `M3`, `8` gives ISO 4762 M3 x 8), never by
  its label;
- any other bought part by its `Designation`, which its script builds from
  its own dimensions;
- a note an assembly carries (`BomNotes`, `fcasm.Assembly.note`), such as
  what it leaves out, is printed under the tables.
"""

import json
import os
import re
import sys
import traceback

ROOT = os.environ["FCROOT"]
sys.path.insert(0, os.path.join(ROOT, "code", "lib"))

import DraftVecUtils  # noqa: E402,F401  (before anything loads the Fasteners add-on)
import FreeCAD as App  # noqa: E402

import fcasm  # noqa: E402
import fcprim  # noqa: E402
import paths  # noqa: E402


def say(*a):
    print("\n" + " ".join(str(x) for x in a), flush=True)


def _members(asm):
    """The parts, fasteners and sub-assembly links an assembly holds itself:
    not the child links FreeCAD makes inside a sub-assembly link, which stand
    for the sub-assembly's own parts."""
    inside = set()
    for o in asm.Group:
        if o.TypeId == "Assembly::AssemblyLink":
            inside.update(c.Name for c in o.Group)
    return [o for o in asm.Group if o.Name not in inside and
            (o.TypeId in ("App::Link", "Assembly::AssemblyLink") or fcasm.is_fastener(o))]


def _standard(kind):
    m = re.match(r"^(ISO|DIN|EN|ASME|GB)(\S+)$", kind)
    return f"{m.group(1)} {m.group(2)}" if m else kind


def _length(fastener):
    """A screw's length is an enumeration ("8", or "Custom" and LengthCustom),
    and the add-on keeps LengthCustom equal to it either way; an insert's is a
    plain length."""
    if fastener.getTypeIdOfProperty("Length") == "App::PropertyEnumeration":
        return float(fastener.LengthCustom.Value)
    return float(getattr(fastener.Length, "Value", fastener.Length))


def _material(obj):
    kind = getattr(obj, "PartMaterial", None)
    return fcprim.material_name(kind) if kind in fcprim.PROJECT.MATERIALS else ""


def count(top):
    """{(group, key): row} for everything under assembly `top`, with counts."""
    rows, notes = {}, []

    def add(group, key, row, n):
        r = rows.setdefault((group, key), dict(row, qty=0))
        r["qty"] += n

    def walk(asm, n):
        for text in getattr(asm, "BomNotes", []):
            if text not in notes:
                notes.append(text)
        for o in _members(asm):
            group = fcasm.category(o)
            if group == "Assemblies":
                sub = o.LinkedObject
                add(group, sub.Document.Name, {
                    "assembly": sub.Label, "document": paths.rel(sub.Document.FileName)}, n)
                walk(sub, n)
            elif group == "Norm_parts":
                length = _length(o)
                add(group, (o.Type, o.Diameter, round(length, 3)), {
                    "fastener": getattr(o.Proxy, "familyType", "") or "",
                    "standard": _standard(o.Type), "size": f"{o.Diameter} x {length:g}",
                    "diameter": o.Diameter, "length": round(length, 3),
                    "material": _material(o)}, n)
            else:
                part = o.getLinkedObject(True)
                doc = part.Document
                add(group, doc.Name, {
                    "part": getattr(part, "Designation", "") or doc.Name,
                    "material": _material(part),
                    "document": paths.rel(doc.FileName)}, n)

    walk(top, 1)
    return rows, notes


def _number(text):
    m = re.search(r"[\d.]+", text)
    return float(m.group(0)) if m else 0.0


def table(lines, title, columns, rows, total=True):
    if not rows:
        return
    lines += ["", f"## {title}", "",
              "| " + " | ".join(h for h, _ in columns) + " |",
              "|" + "---|" * len(columns)]
    for r in rows:
        cells = []
        for _, key in columns:
            v = r[key]
            cells.append(f"`{v}`" if key == "document" else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    if total:
        lines.append(f"| **{sum(r['qty'] for r in rows)} in all** |" + " |" * (len(columns) - 1))


def main():
    tops = [p for p in os.environ.get("FCARGS", "").split("|") if p]
    if not tops:
        raise SystemExit("no top-level assembly named")
    lines = ["# Bill of materials", "",
             "Counted from the built assemblies by `code/bom.py` (`python3 code/rebuild.py bom`), "
             "so it changes when they do. The documents named here hold each part."]
    data = []
    for rel in tops:
        doc = App.openDocument(os.path.join(ROOT, rel))
        found = [o for o in doc.Objects if o.TypeId == "Assembly::AssemblyObject"]
        if len(found) != 1:
            raise SystemExit(f"{rel}: {len(found)} assemblies, wanted one")
        rows, notes = count(found[0])
        by = lambda g: [r for (grp, _), r in sorted(rows.items(), key=lambda kv: str(kv[0]))
                        if grp == g]
        printed = sorted(by("Printed_parts"), key=lambda r: r["document"])
        cots = sorted(by("COTS"), key=lambda r: r["part"])
        fasteners = sorted(by("Norm_parts"),
                           key=lambda r: (r["fastener"], r["standard"],
                                          _number(r["diameter"]), r["length"]))
        subs = sorted(by("Assemblies"), key=lambda r: r["document"])
        if len(tops) > 1:
            lines += ["", f"# {found[0].Label}"]
        else:
            lines[-1] += f" Assembly: `{rel}`."
        table(lines, "Printed parts", [("Part", "part"), ("Material", "material"),
                                       ("Quantity", "qty"), ("Document", "document")], printed)
        table(lines, "Bought parts", [("Part", "part"), ("Quantity", "qty"),
                                      ("Document", "document")], cots)
        table(lines, "Screws and inserts", [("Fastener", "fastener"), ("Standard", "standard"),
                                            ("Size", "size"), ("Material", "material"),
                                            ("Quantity", "qty")], fasteners)
        table(lines, "Sub-assemblies, for orientation (their parts are counted above)",
              [("Assembly", "assembly"), ("Quantity", "qty"), ("Document", "document")], subs,
              total=False)
        if notes:
            lines += ["", "## Not counted", ""] + [f"- {t}" for t in notes]
        data.append({"assembly": rel, "printed": printed, "bought": cots,
                     "fasteners": fasteners, "assemblies": subs, "notes": notes})
        say(f"  bom: {rel}: {sum(r['qty'] for r in printed)} printed parts, "
            f"{sum(r['qty'] for r in cots)} bought parts, "
            f"{sum(r['qty'] for r in fasteners)} screws and inserts")
    with open(os.path.join(ROOT, "BOM.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.makedirs(paths.BUILD_DATA, exist_ok=True)
    with open(os.path.join(os.path.dirname(paths.BUILD_DATA), "bom.json"), "w") as fh:
        json.dump(data, fh, indent=1)
        fh.write("\n")


try:
    main()
    say("BOM OK")
except BaseException:
    say(traceback.format_exc())
    say("BOM FAILED")
