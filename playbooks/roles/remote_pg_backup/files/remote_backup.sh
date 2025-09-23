#!/bin/bash

check_env_var() {
  local var_name="$1"

  if [[ -z "${!var_name}" ]]; then
    echo "Error: Environment variable '$var_name' is not set or is empty."
    return 1
  else
    return 0
  fi
}

on_error() {
  echo $1
  curl -d "remote db backup failed" https://ntfy.rileymathews.com/home-server-alerts
}

echo "starting remote database backup"

set -e
trap 'on_error' ERR

check_env_var "AWS_ACCESS_KEY_ID"
check_env_var "AWS_SECRET_ACCESS_KEY"
check_env_var "AWS_ENDPOINT_URL"

backup_database() {
    local host=$1
    local port=$2
    local database_name=$3
    local username=$4
    local password=$5

    current_date=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
    backup_dir=/tmp/db_backups/$database_name
    backup_output_name=$current_date
    backup_full_output_dir=$backup_dir/$backup_output_name
    tar_file_name=$backup_output_name.tar.gz

    mkdir -p $backup_dir
    cd $backup_dir

    echo "backing up database $database_name from $host:$port to directory $backup_dir outputing to $backup_output_name"

    # Set password for pg_dump
    export PGPASSWORD="$password"

    pg_dump \
        --host="$host" \
        --port="$port" \
        --username="$username" \
        --format=directory \
        --create \
        --clean \
        --if-exists \
        --file="$backup_output_name" \
        "$database_name"

    # Clear password from environment
    unset PGPASSWORD

    tar -czvf $tar_file_name $backup_output_name

    aws s3 cp $tar_file_name "s3://postgres-backups/$database_name/$tar_file_name"

    echo "Successfully backed up $database_name from $host:$port"
}

echo "starting postgres backup"

# Read database configurations from JSON file
if [[ ! -f /var/lib/backup/databases.json ]]; then
    echo "Error: /var/lib/backup/databases.json not found"
    exit 1
fi

# Parse JSON and backup each database
jq -r '.[] | "\(.host)|\(.port // 5432)|\(.name)|\(.user)|\(.password)"' /var/lib/backup/databases.json | \
while IFS='|' read -r host port database_name username password; do
    if [[ -n "$database_name" ]]; then
        backup_database "$host" "$port" "$database_name" "$username" "$password"
    fi
done

rm -rf /tmp/db_backups
echo "All database backups completed successfully"
exit 0

# to restore a database. Download the file, unzip it, and run
# pg_restore --dbname=<database> --clean --if-exists --format=directory --jobs=4 backup_dir