#!/usr/bin/env bash
set -euo pipefail

SOURCE=""
DEST=""
KEEP=5
DRY_RUN=false
 
usage() {
  echo "Usage: $0 --source <path> --dest <path> [--keep <N>] [--dry-run] [--help]"
  echo "  --source   Source directory to back up (required)"
  echo "  --dest     Destination directory for archives (required)"
  echo "  --keep     Number of recent backups to retain (default: 5)"
  echo "  --dry-run  Show planned actions without making changes"
  echo "  --help     Show this help message"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    --keep) KEEP="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help) usage ;;
    *) echo "Error: Unknown option $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$SOURCE" || -z "$DEST" ]]; then
  echo "Error: Parameters --source and --dest are required!" >&2
  exit 2
fi

if [[ ! -d "$SOURCE" || ! -r "$SOURCE" ]]; then
  echo "Error: Source directory '$SOURCE' does not exist or is not readable." >&2
  exit 3
fi

if [[ ! -d "$DEST" ]]; then
  if $DRY_RUN; then
    echo "[DRY-RUN] Would create destination directory: $DEST"
  else
    mkdir -p "$DEST"
  fi
fi

SRC_NAME=$(basename "$SOURCE")
TIMESTAMP=$(date +"%Y-%m-%d-%H%M%S")
ARCHIVE_NAME="${SRC_NAME}-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${DEST}/${ARCHIVE_NAME}"

COUNTER=1
while [[ -e "$ARCHIVE_PATH" ]]; do
  ARCHIVE_NAME="${SRC_NAME}-${TIMESTAMP}_${COUNTER}.tar.gz"
  ARCHIVE_PATH="${DEST}/${ARCHIVE_NAME}"
  COUNTER=$((COUNTER + 1))
done

if $DRY_RUN; then
  echo "[DRY-RUN] Would create archive: $ARCHIVE_PATH"
else
  tar -czf "$ARCHIVE_PATH" -C "$(dirname "$SOURCE")" "$(basename "$SOURCE")"
fi

EXISTING_BACKUPS=()
if [[ -d "$DEST" ]]; then
  while IFS= read -r -d '' file; do
    EXISTING_BACKUPS+=("$file")
  done < <(find "$DEST" -maxdepth 1 -type f -name "${SRC_NAME}-*.tar.gz" -print0 | sort -z)
fi

TOTAL_BACKUPS=${#EXISTING_BACKUPS[@]}
DELETED_COUNT=0

if (( TOTAL_BACKUPS > KEEP )); then
  REMOVE_COUNT=$(( TOTAL_BACKUPS - KEEP ))
  for (( i=0; i<REMOVE_COUNT; i++ )); do
    FILE_TO_REMOVE="${EXISTING_BACKUPS[$i]}"
    if $DRY_RUN; then
      echo "[DRY-RUN] Would delete old archive: $FILE_TO_REMOVE"
    else
      rm -f "$FILE_TO_REMOVE"
    fi
    DELETED_COUNT=$((DELETED_COUNT + 1))
  done
fi

SIZE="0B"
if ! $DRY_RUN && [[ -f "$ARCHIVE_PATH" ]]; then
  SIZE=$(du -h "$ARCHIVE_PATH" | cut -f1)
fi

echo "$(date +'%Y-%m-%d %H:%M:%S') | ACTION: backup | SOURCE: $SOURCE | CREATED: $ARCHIVE_NAME ($SIZE) | DELETED: $DELETED_COUNT | DRY_RUN: $DRY_RUN"
exit 0
