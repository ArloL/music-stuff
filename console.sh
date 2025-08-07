#!/bin/sh
set -o errexit

rm -f beaTunes-F17A2D52DA187A20.*.db
cp -c "${HOME}/Library/Application Support/beaTunes/Database/beaTunes-F17A2D52DA187A20.h2.db" beaTunes-F17A2D52DA187A20.h2.db
java -cp "/Applications/beaTunes5.app/Contents/Java/h2-1.4.195.jar" "org.h2.tools.Console" -url "jdbc:h2:~/Developer/beatunes-dbviewer/beaTunes-F17A2D52DA187A20" -user sa -password "" -browser -webPort 56547
