#!/bin/bash

set -o errexit
set -o nounset
set -o xtrace

cd "$(dirname "$0")/.." || exit 1

rm -f ./tmp/beaTunes.*.db

files=("${HOME}/Library/Application Support/beaTunes/Database/"beaTunes-*.h2.db)
if (( ${#files[@]} != 1 )); then
  echo "Expected exactly 1 db file, found ${#files[@]}" >&2
  exit 1
fi

cp -c "${files[0]}" ./tmp/beaTunes.h2.db

rm -f ./tmp/djay-MediaLibrary.*

files=("${HOME}/Music/djay/djay Media Library.djayMediaLibrary/MediaLibrary.db")
if (( ${#files[@]} != 1 )); then
  echo "Expected exactly 1 db file, found ${#files[@]}" >&2
  exit 1
fi

cp -c "${files[0]}" ./tmp/djay-MediaLibrary.db
