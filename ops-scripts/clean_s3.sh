#!/bin/bash

# Check if bucket name is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <bucket-name>"
    exit 1
fi

BUCKET_NAME=$1

# Check if the bucket exists
if ! aws s3 ls "s3://$BUCKET_NAME" &> /dev/null; then
    echo "Error: Bucket '$BUCKET_NAME' does not exist."
    exit 1
fi

echo "Deleting all objects in bucket: $BUCKET_NAME..."

# Delete all objects in the bucket
aws s3 rm "s3://$BUCKET_NAME" --recursive

if [ $? -ne 0 ]; then
    echo "Error: Failed to delete objects in bucket '$BUCKET_NAME'."
    exit 1
fi

echo "All objects deleted successfully."

echo "Deleting the bucket: $BUCKET_NAME..."

# Delete the bucket
aws s3 rb "s3://$BUCKET_NAME"

if [ $? -ne 0 ]; then
    echo "Error: Failed to delete bucket '$BUCKET_NAME'."
    exit 1
fi

echo "Bucket '$BUCKET_NAME' deleted successfully."

