#!/bin/bash
set -euo pipefail

#require all three arguments
if [ $# -lt 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRATION_SECONDS"
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRATION="$3"

#download the book into books/, keeping the name from the URL
FILENAME=$(basename "$URL")
mkdir -p books
curl -sL "$URL" -o "books/$FILENAME"

#create bucket
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
	echo "Bucket already exists: $BUCKET"
else
	aws s3 mb "s3://$BUCKET"
fi

#uploading the book as plain text
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" --content-type "text/plain; charset=utf-8"

#print time-limited presigned URL
aws s3 presign "s3://$BUCKET/$FILENAME" --expires-in="$EXPIRATION"
