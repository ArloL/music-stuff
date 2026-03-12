#!/bin/bash

set -o errexit
set -o nounset
set -o xtrace

cd "$(dirname "$0")/" || exit 1

rm -f "scripts/tmp/"beaTunes.*.db

files=("${HOME}/Library/Application Support/beaTunes/Database/"beaTunes-*.h2.db)
if (( ${#files[@]} != 1 )); then
  echo "Expected exactly 1 db file, found ${#files[@]}" >&2
  exit 1
fi
cp -c "${files[0]}" scripts/tmp/beaTunes.h2.db

java -cp "/Applications/beaTunes5.app/Contents/Java/"h2-*.jar \
    "org.h2.tools.Console" \
    -url "jdbc:h2:~/Developer/beatunes-dbviewer/scripts/tmp/beaTunes" \
    -user sa \
    -password "" \
    -browser \
    -webPort 56547
