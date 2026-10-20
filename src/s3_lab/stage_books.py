#!/usr/bin/env python3

import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read the book list, index page, and bucket name"""
    if len(sys.argv) < 4:
        log.error(f"Usage: {sys.argv[0]} BOOK_LIST_FILE INDEX_HTML BUCKET_NAME")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download each book URL to dest_dir and return the local file paths."""
    os.makedirs(dest_dir, exist_ok=True)

    try:
        with open(list_file) as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        log.error(f"Book list not found: {list_file}")
        return []

    log.info(f"Found {len(urls)} book URLs in {list_file}")
    paths = []

    for url in urls:
        filename = url.rstrip("/").split("/")[-1]
        path = os.path.join(dest_dir, filename)

        if os.path.exists(path):
            log.info(f"Already downloaded")
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as out:
                out.write(response.content)
            log.info(f"Downloaded {url} -> {path}")
            paths.append(path)
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")

        time.sleep(1)

    log.info(f"{len(paths)} of {len(urls)} books available in {dest_dir}/")
    return paths


def create_bucket(bucket):
    """Creates S3 bucker if needed"""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket already exists: {bucket}")
        return True
    except ClientError:
        pass

    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket {bucket}: {e}")
        return False


def make_public(bucket):
    """Makes bucket public to read"""
    try:
        s3.put_public_access_block(
            	Bucket=bucket,
		PublicAccessBlockConfiguration={
		"BlockPublicAcls": False,
		"IgnorePublicAcls": False,
		"BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Made bucket public: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error making bucket {bucket} public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload the downloaded books to the top level of the bucket."""
    count = 0

    for path in file_paths:
        filename = os.path.basename(path)
        try:
            with open(path, "rb") as f:
                s3.put_object(
                    Bucket=bucket,
                    Key=filename,
                    Body=f,
                    ContentType="text/plain; charset=utf-8",
                )
            log.info(f"Uploaded {path} to s3://{bucket}/{filename}")
            count += 1
        except FileNotFoundError:
            log.error(f"Local file not found: {path}")
        except ClientError as e:
            log.error(f"Error uploading {path}: {e}")

    log.info(f"Uploaded {count} of {len(file_paths)} books")
    return count


def upload_index(bucket, index_path):
    """Upload the HTML index page as index.html."""
    try:
        with open(index_path, "rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key="index.html",
                Body=f,
                ContentType="text/html",
            )
        log.info(f"Uploaded {index_path} to s3://{bucket}/index.html")
        return True
    except FileNotFoundError:
        log.error(f"Local file not found: {index_path}")
    except ClientError as e:
        log.error(f"Error uploading index page: {e}")

    return False


def main():
    """Run the steps to stage the books in S3."""
    list_file, index_path, bucket = parse_args()

    book_paths = download_books(list_file, "books")
    if not book_paths:
        log.error("No books were downloaded; stopping.")
        sys.exit(1)

    if not create_bucket(bucket):
        log.error(f"Could not create bucket {bucket}; stopping.")
        sys.exit(1)

    if not make_public(bucket):
        log.error(f"Could not make bucket {bucket} public; stopping.")
        sys.exit(1)

    uploaded = upload_files(bucket, book_paths)
    index_ok = upload_index(bucket, index_path)

    url = f"https://{bucket}.s3.amazonaws.com/index.html"
    if index_ok and uploaded == len(book_paths):
        log.info(f"Success: staged {uploaded} books. Browse them at {url}")
    else:
        log.error(
            f"Finished with errors: {uploaded}/{len(book_paths)} books uploaded, "
            f"index {'uploaded' if index_ok else 'NOT uploaded'}. URL: {url}"
	)
	
if __name__ == "__main__":
	main()