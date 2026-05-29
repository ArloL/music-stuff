#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

andme="id:37i9dQZF1DXdf6bvyXShR3"
anotr="id:37i9dQZF1DWTfGx5o2qjVb"
AxelBoman="id:37i9dQZF1DXccw7SlFjeWF"
BarryCantSwim="id:37i9dQZF1DWVbfVJ3tB3QO"
BellaBoo="id:37i9dQZF1DWYZhaTaHlh27"
BlackCoffee="id:37i9dQZF1DXc8VZ9nbXQ1z"
Daphni="id:37i9dQZF1DWTQHB0vBt1AG"
DJBoring="id:37i9dQZF1DX00RdhV73Dbe"
DJHell="id:1iarTWt8gQd6gcAUTMmGEt"
DJSeinfeld="id:37i9dQZF1DWVInERw2ZCfq"
FredAgain="id:3cakkcelZt3C857q5YKPjF"
GerdJanson="id:37i9dQZF1DX8A9EbZP1hul"
GuiBoratto="id:37i9dQZF1DX4fgrmoIzHtd"
HoneyDijon="id:37i9dQZF1DWTYPRTIhI2jZ"
Jamiexx="id:37i9dQZF1DXcIJGgaOURNE"
JaydaG="id:37i9dQZF1DX0F8FtqyAjxC"
KellyLeeOwens="id:37i9dQZF1DWYMVjvqDxZQX"
LaurentGarnier="id:37i9dQZF1DX68l5gg4hq38"
Logic1000="id:37i9dQZF1DWWbEGrb2ydWx"
MaceoPlex="id:37i9dQZF1DWUomyMFpoR0R"
MarcelDettmann="id:37i9dQZF1DX2MrqV1P93C9"
MayaJaneColes="id:37i9dQZF1DWZkxJwAfCZA3"
MissKittin="id:37i9dQZF1DWW9AqVvhy1Jb"
Modeselektor="id:37i9dQZF1DWXl7Y0piXYnl"
NinaKraviz="id:37i9dQZF1DX717gvXLoUJP"
PeggyGou="id:7u9B9jIeF5b3IMcm6PqoVu"
SofiaKourtesis="id:37i9dQZF1DWVFhnU8yozBd"

uv run spotify-browser-add-to-playlist --headless \
    "Recommended" \
    "${andme}" \
    "${anotr}" \
    "${AxelBoman}" \
    "${BarryCantSwim}" \
    "${BellaBoo}" \
    "${BlackCoffee}" \
    "${Daphni}" \
    "${DJBoring}" \
    "${DJHell}" \
    "${DJSeinfeld}" \
    "${FredAgain}" \
    "${GerdJanson}" \
    "${GuiBoratto}" \
    "${HoneyDijon}" \
    "${Jamiexx}" \
    "${JaydaG}" \
    "${KellyLeeOwens}" \
    "${LaurentGarnier}" \
    "${Logic1000}" \
    "${MaceoPlex}" \
    "${MarcelDettmann}" \
    "${MayaJaneColes}" \
    "${MissKittin}" \
    "${Modeselektor}" \
    "${NinaKraviz}" \
    "${PeggyGou}" \
    "${SofiaKourtesis}"
