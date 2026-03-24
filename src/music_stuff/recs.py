from music_stuff.lib.lib_reccobeats import (
    get_audio_features,
    get_reccobeats_id,
    get_recommendation,
    get_track_detail,
)

cant_see_what_is_burning_there = "4LTt3LIHKYhD2D1Mgfg2s1"
peace_u_need = "4A8tKYA7gwZzQ4jVwIv1sv"
track_detail = get_track_detail(get_reccobeats_id(cant_see_what_is_burning_there))
rec = get_recommendation(track_detail["id"])
# print(json.dumps(rec, indent=1))
for track in rec:
    track["audio_features"] = get_audio_features([track["id"]])
    print(
        f"{', '.join([d['name'] for d in track['artists']])} - {track['trackTitle']}: {track['href']}"
    )
