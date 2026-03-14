#!/bin/bash

set -o errexit
set -o nounset
set -o xtrace

cd "$(dirname "$0")/" || exit 1

sh ./clone-dbs.sh

java -cp "/Applications/beaTunes5.app/Contents/Java/"h2-*.jar \
    "org.h2.tools.Shell" \
    -help
