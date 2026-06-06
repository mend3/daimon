#!/usr/bin/env bash
# Back up the Qdrant storage volume to ~/hermes-backups, keeping the 14 most
# recent. Qdrant is a rebuildable index — the SQLite ledger in hermes-data (backed
# up by backup-hermes.sh) is the source of truth — so this snapshot just avoids
# re-embedding on restore. Run on demand or daily alongside backup-hermes.sh.
set -euo pipefail

DEST="${HOME}/hermes-backups"
VOLUME="hermes-qdrant_qdrant-data"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${DEST}"

if ! docker volume inspect "${VOLUME}" >/dev/null 2>&1; then
  echo "Qdrant volume ${VOLUME} not found — nothing to back up."
  exit 0
fi

docker run --rm \
  -v "${VOLUME}:/data:ro" \
  -v "${DEST}:/backup" \
  alpine tar czf "/backup/qdrant-data-${STAMP}.tgz" -C /data .

ls -1t "${DEST}"/qdrant-data-*.tgz 2>/dev/null | tail -n +15 | xargs -I{} rm -f {} 2>/dev/null || true

echo "Backup written: ${DEST}/qdrant-data-${STAMP}.tgz"
echo "Restore: docker run --rm -v ${VOLUME}:/data -v ${DEST}:/backup alpine \\"
echo "         sh -c 'rm -rf /data/* && tar xzf /backup/<file>.tgz -C /data'  (then restart Qdrant)"
