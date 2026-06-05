#!/usr/bin/env bash
# Back up the hermes-data volume (~/.hermes: config, memories, sessions, .env)
# to ~/hermes-backups, keeping the 14 most recent. Run on demand or daily by the
# com.hermes.backup LaunchAgent.
set -euo pipefail

DEST="${HOME}/hermes-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${DEST}"

docker run --rm \
  -v hermes-data:/data:ro \
  -v "${DEST}:/backup" \
  alpine tar czf "/backup/hermes-data-${STAMP}.tgz" -C /data .

# Keep the 14 newest archives.
ls -1t "${DEST}"/hermes-data-*.tgz 2>/dev/null | tail -n +15 | xargs -I{} rm -f {} 2>/dev/null || true

echo "Backup written: ${DEST}/hermes-data-${STAMP}.tgz"
echo "Restore: docker run --rm -v hermes-data:/data -v ${DEST}:/backup alpine \\"
echo "         sh -c 'rm -rf /data/* && tar xzf /backup/<file>.tgz -C /data'"
