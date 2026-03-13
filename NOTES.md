## Domain concepts

**Open Key notation** — keys are expressed as `1d`–`12d` (major) and `1m`–`12m` (minor), corresponding to positions on the circle of fifths. All sources normalise to this format.

**Key consensus** (`lib_consensus.py`) — weighted vote across 9 independent algorithms: 7 Essentia profiles (weighted by their strength score, typically 0.77–0.90) plus djay and beaTunes (each weighted 0.5 as less reliable).

**BPM consensus** — normalises octave errors (halving/doubling) before averaging across sources.

**Essentia cache** — analysis results are stored in `data/lib_essentia_cache.csv`. Already-cached songs are skipped. Delete an entry (or the whole file) to force re-analysis.

**`key_diff`** — sum of circular distances from `effective_key` to each source key. A single outlier contributes its own distance once, not amplified by every other source.

## Spotify API: playlist_remove_specific_occurrences_of_items does not work

Tried using
`sp.playlist_remove_specific_occurrences_of_items(playlist_id, [{uri, positions}])`
to remove only duplicate positions while keeping the first occurrence. Despite
passing exact positions, it removed **all** occurrences of the track rather
than just the specified positions.

## Queries

```
SELECT COMMENTS, TONALKEY FROM SONGS GROUP BY TONALKEY, COMMENTS ORDER BY TONALKEY

-- sun harmonics
SELECT ARTIST, NAME, COMMENTS, TONALKEY, EXACTBPM, GENRE, * FROM SONGS WHERE ID = '-1754864623550005176'
-- yali: 6008492067627959237
-- dont eat the homies: 7045391083672295624

SELECT ARTIST, NAME, COMMENTS, TONALKEY, EXACTBPM, * FROM SONGS WHERE
    EXACTBPM BETWEEN 114 AND 122
AND GENRE IN ('Electronic', 'Ambient')
AND RATING = 100
AND COMMENTS != 'ignore'
AND COMMENTS NOT LIKE '%mixed%'
AND TONALKEY IN (3,4,5,7,21)
```

## essentia confidence of RhythmExtractor2013 with BeatTrackerMultiFeature (default)

Copied from <https://essentia.upf.edu/reference/std_BeatTrackerMultiFeature.html>:

    You can follow these guidelines [2] to assess the quality of beats estimation based on the computed confidence value:

    * [0, 1) very low confidence, the input signal is hard for the employed candidate beat trackers
    * [1, 1.5] low confidence
    * (1.5, 3.5] good confidence, accuracy around 80% in AMLt measure
    * (3.5, 5.32] excellent confidence


## beaTunes ID vs Apple Music Persistent ID

beaTunes stores song IDs with the sign bit (bit 63) flipped compared to the Apple Music persistent ID.
This is the difference between two's complement and offset binary encoding.

    beatunes_id = apple_music_persistent_id ^ 0x8000000000000000

Example for "Never Said Goodbye (Lee Waxman's Long Hot Disco Mix)" by Dorothy's Ghost:
    Apple Music persistent ID (signed): -5639804195476274594  (hex: B1BB63F715E1025E)
    beaTunes internal ID:                3583567841378501214  (hex: 31BB63F715E1025E)

The XOR of the two values is exactly 0x8000000000000000 (2^63). The operation is its own inverse.

## Tonalkey

* 0 == Not analyzed
* 1 == 1d
* 2 == 1m
* 3 == 2d
* 4 == 2m
* 5 == 3d
* 6 == 3m
* 7 == 4d
* 8 == 4m
* 9 == 5d
* 10 == 5m
* 11 == 6d
* 12 == 6m
* 13 == 7d
* 14 == 7m
* 15 == 8d
* 16 == 8m
* 17 == 9d
* 18 == 9m
* 19 == 10d
* 20 == 10m
* 21 == 11d
* 22 == 11m
* 23 == 12d
* 24 == 12m
