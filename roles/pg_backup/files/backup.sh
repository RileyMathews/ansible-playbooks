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
    DATABASE_NAME=$1
    current_date=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
    backup_dir=/tmp/db_backups/$DATABASE_NAME
    backup_output_name=$current_date
    backup_full_output_dir=$backup_dir/$backup_output_name
    tar_file_name=$backup_output_name.tar.gz

    mkdir -p $backup_dir
    cd $backup_dir

    echo "backing up database $DATABASE_NAME to directory $backup_dir outputing to $backup_output_name"
    pg_dump --format=directory --create --clean --if-exists --file=$backup_output_name $DATABASE_NAME

    tar -czvf $tar_file_name $backup_output_name

    aws s3 cp $tar_file_name "s3://postgres-backups/$DATABASE_NAME/$tar_file_name"

    curl https://ntfy.rileymathews.com/home-server-alerts -d "$DATABASE_NAME db backup finished."
}

echo "starting postgres backup"
backup_database "riley"
exit 0

# to restore a database. Download the file, unzip it, and run
# pg_restore --dbname=<database> --clean --if-exists --format=directory --jobs=4 backup_dir
