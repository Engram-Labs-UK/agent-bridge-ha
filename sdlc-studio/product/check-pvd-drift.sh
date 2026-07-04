#!/usr/bin/env bash
# Standing seam-check: this repo's read-only PVD projection vs the master in engram-labs-product.
# Self-contained - no sdlc-studio skill needed. The projection is written read-only by
# `sync-projections.sh` (run in engram-labs-product after the master PVD is edited).
#   exit 0  in-sync, OR the master repo is not checked out beside this one (advisory)
#   exit 1  the projection is stale or missing (re-sync required)
set -u
here="$(cd "$(dirname "$0")" && pwd)"                      # <repo>/sdlc-studio/product
projection="$here/pvd.md"
master="$here/../../../engram-labs-product/sdlc-studio/product/pvd.md"
if [ ! -f "$master" ]; then
  echo "pvd-drift: master not checked out beside this repo - skipping (advisory)"; exit 0
fi
if [ ! -f "$projection" ]; then
  echo "pvd-drift: FAIL - projection missing; run engram-labs-product/sdlc-studio/product/sync-projections.sh"; exit 1
fi
if cmp -s "$master" "$projection"; then
  echo "pvd-drift: in-sync"; exit 0
fi
echo "pvd-drift: FAIL - the product PVD projection is STALE (master moved on)."
echo "  re-sync: bash engram-labs-product/sdlc-studio/product/sync-projections.sh"
exit 1
