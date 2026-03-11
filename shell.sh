#!/bin/sh
set -o errexit

rm -f scripts/tmp/beaTunes.*.db
cp -c "${HOME}/Library/Application Support/beaTunes/Database/"beaTunes-*.h2.db \
    scripts/tmp/beaTunes.h2.db
java -cp "/Applications/beaTunes5.app/Contents/Java/"h2-*.jar \
    "org.h2.tools.Shell" \
    -help
