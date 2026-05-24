#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

cd "$(dirname "$0")/" || exit 1

sh spotify-follow-djs.sh
sh spotify-recommended.sh
sh spotify-radio.sh
sh spotify-weekly.sh
sh spotify-cleanup.sh
