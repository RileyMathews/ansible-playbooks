#! /bin/bash

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
  curl -d "db backup failed" https://ntfy.rileymathews.com/home-server-alerts
}

echo "starting backup"

set -e
trap 'on_error' ERR

check_env_var "AWS_ACCESS_KEY_ID"
check_env_var "AWS_SECRET_ACCESS_KEY"
check_env_var "AWS_ENDPOINT_URL"

backup_database() {
    local db_config="$1"
    
    # Parse database configuration from JSON
    local database_name=$(echo "$db_config" | jq -r '.name')
    local db_host=$(echo "$db_config" | jq -r '.host // "localhost"')
    local db_port=$(echo "$db_config" | jq -r '.port // 5432')
    local db_user=$(echo "$db_config" | jq -r '.user // .name')
    local db_password=$(echo "$db_config" | jq -r '.password // empty')
    
    if [[ -z "$database_name" || "$database_name" == "null" ]]; then
        echo "Error: Database name is required"
        return 1
    fi
    
    current_date=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
    backup_dir=/tmp/db_backups/$database_name
    backup_output_name=$current_date
    backup_full_output_dir=$backup_dir/$backup_output_name
    tar_file_name=$backup_output_name.tar.gz

    mkdir -p $backup_dir
    cd $backup_dir

    # Build pg_dump command with connection parameters
    local pg_dump_cmd="pg_dump --format=directory --create --clean --if-exists --file=$backup_output_name"
    
    pg_dump_cmd="$pg_dump_cmd --host=$db_host --port=$db_port --username=$db_user"
    pg_dump_cmd="$pg_dump_cmd $database_name"

    echo "backing up database $database_name from $db_host:$db_port as user $db_user"
    echo "output directory: $backup_dir/$backup_output_name"
    
    # Set password if provided
    if [[ -n "$db_password" && "$db_password" != "null" ]]; then
        PGPASSWORD="$db_password" $pg_dump_cmd
    else
        $pg_dump_cmd
    fi

    tar -czvf $tar_file_name $backup_output_name

    aws s3 cp $tar_file_name "s3://postgres-backups/$database_name/$tar_file_name"
    
    echo "Successfully backed up $database_name"
}

echo "starting postgres backup"

# Read database configurations from JSON array
jq -c '.[]' /var/lib/backup/databases.json | while read -r db_config; do
    backup_database "$db_config"
done

rm -rf /tmp/db_backups
exit 0

# to restore a database. Download the file, unzip it, and run
# pg_restore --host=HOST --port=PORT --username=USER --dbname=DATABASE --clean --if-exists --format=directory --jobs=4 backup_dir