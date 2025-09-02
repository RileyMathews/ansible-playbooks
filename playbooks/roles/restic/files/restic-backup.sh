#!/bin/bash

on_error() {
  echo $1
  curl -d "restic backup failed" https://ntfy.rileymathews.com/home-server-alerts
}

echo "starting backup"

set -e
trap 'on_error' ERR

file_path="/etc/restic-backup/directories.txt"
export RESTIC_REPOSITORY="s3:https://37a8e358fee81bf1f20e08b6ffe72c1d.r2.cloudflarestorage.com/restic-backups"
export RESTIC_PASSWORD_FILE=/var/lib/restic-backups/password
export HOME=/root
hostname=$(hostname)
source /var/lib/restic-backups/env

while IFS= read -r dir; do
    # Do something with each line
    echo "Processing: $dir"
    restic backup $dir
done < "$file_path"

echo "done!"
