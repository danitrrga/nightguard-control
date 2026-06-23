#!/usr/bin/env python3
"""PoC: extract a nightguard-usable blocklist from a StayFree settings export.
Read-only. Classifies each rule target as RESOLVABLE (concrete) vs OPAQUE (needs StayFree cloud)."""
import json, sys

export = sys.argv[1]
d = json.load(open(export))
rules = d.get("genericWebsiteLimits", {})

resolvable_urls = set()
opaque = {"categoryIds": set(), "brandIds": set()}
desktop_apps = set()
night_rules = []

for rid, r in rules.items():
    if not r.get("isEnabled"): continue
    for u in r.get("websiteUrls", []): resolvable_urls.add(u)
    for a in r.get("desktopAppIds", []): desktop_apps.add(a)
    for c in r.get("categoryIds", []): opaque["categoryIds"].add(c)
    for b in r.get("brandIds", []): opaque["brandIds"].add(b)
    # is this rule active during a typical curfew (e.g. 21:30-06:45 overnight)?
    sh, eh = r.get("scheduleStartHour",0), r.get("scheduleEndHour",0)
    overnight = (sh > eh) or r.get("scheduleIsAllDay")
    if overnight:
        night_rules.append((rid, sh, r.get("scheduleStartMinute",0), eh, r.get("scheduleEndMinute",0),
                            len(r.get("websiteUrls",[])), len(r.get("categoryIds",[]))+len(r.get("brandIds",[]))))

print("=== WHAT A SYNC SCRIPT COULD APPLY TODAY ===")
print(f"\n[OK] Concrete website URLs -> URLBlocklist  ({len(resolvable_urls)}):")
for u in sorted(resolvable_urls): print("       ", u)
print(f"\n[OK] Desktop app IDs -> Hyprland class map  ({len(desktop_apps)}):")
print("        (none)" if not desktop_apps else "\n".join("        "+a for a in sorted(desktop_apps)))
print(f"\n[BLOCKED] Opaque IDs needing StayFree cloud to resolve to domains:")
print(f"        categoryIds: {sorted(opaque['categoryIds'])}")
print(f"        brandIds   : {sorted(opaque['brandIds'])}")
print(f"\n=== OVERNIGHT / CURFEW-RELEVANT RULES ===")
for rid,sh,sm,eh,em,nurls,nopaque in night_rules:
    print(f"   rule {rid}: {sh:02d}:{sm:02d}-{eh:02d}:{em:02d}  concrete_urls={nurls}  opaque_ids={nopaque}")
print("\n=== VERDICT ===")
tot_targets = len(resolvable_urls)+len(desktop_apps)+len(opaque['categoryIds'])+len(opaque['brandIds'])
syncable = len(resolvable_urls)+len(desktop_apps)
print(f"   syncable now: {syncable}/{tot_targets} targets  ({100*syncable//max(tot_targets,1)}%)")
print(f"   the curfew-window rule is {'100% opaque (0 syncable)' if night_rules and night_rules[0][5]==0 else 'partially syncable'}")
