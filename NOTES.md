## Domain concepts

**Open Key notation** — keys are expressed as `1d`–`12d` (major) and `1m`–`12m` (minor), corresponding to positions on the circle of fifths. All sources normalise to this format.

**Key consensus** (`lib_consensus.py`) — weighted vote across 9 independent algorithms: 7 Essentia profiles (weighted by their strength score, typically 0.77–0.90) plus djay and beaTunes (each weighted 0.5 as less reliable).

**BPM consensus** — normalises octave errors (halving/doubling) before averaging across sources.

**Essentia cache** — analysis results are stored in `data/lib_essentia_cache.csv`. Already-cached songs are skipped. Delete an entry (or the whole file) to force re-analysis.

**`key_diff`** — sum of circular distances from `effective_key` to each source key. A single outlier contributes its own distance once, not amplified by every other source.

## djay MediaLibrary.db — TSAF binary format and automix cue points

djay stores everything in a single SQLite file (`MediaLibrary.db`) with a `database2` table:

```
database2(rowid, collection, key, data, metadata)
```

All data is in `data` as TSAF binary blobs.  Key collections:

| collection | purpose |
|---|---|
| `mediaItemAnalyzedData` | BPM, key, beat grid |
| `mediaItemUserData` | per-track DJ settings (cues, play count, colour) |
| `localMediaItemLocations` | file path + Apple Music persistent ID |
| `historySessions` | DJ set sessions |
| `historySessionItems` | individual tracks played in each session |

 The `key` is **not** the Apple Music persistent ID.

### Finding a track

To find a specific track, look at the `localMediaItemLocations` collection.
It contains the Apple Music persistent ID as decimal in the blob data:
`\x08com.apple.iTunes:PERSISTENT_ID_DECIMAL\x00`.
For example to get the hexadecimal song id BCF4FFC5EFDDC171,
first convert it to decimal (13615788799045779825) and then query with
`instr` to allow sqlite to search the binary data:

```
select * from database2 where collection = 'localMediaItemLocations' and instr(data, 'com.apple.iTunes:13615788799045779825') > 0
```

### TSAF encoding

TSAF blobs use two encoding modes: **verbose** (string field names) and **compact** (numeric field IDs).

#### Verbose encoding

Fields are encoded as `TYPE_TAG VALUE 0x08 FIELD_NAME 0x00`.  The type tag determines how to read the value:

| type tag | type |
|---|---|
| `0x08 … 0x00` | string (the `0x08` is part of the value, no separate type tag) |
| `0x0B [4 bytes]` | uint32 little-endian |
| `0x13 [4 bytes]` | float32 little-endian |
| `0x13 0x00 [4 bytes]` | float32 little-endian (alternate form) |
| `0x30 0x00 [8 bytes]` | float64 little-endian (Core Data timestamp: seconds since 2001-01-01) |
| `0x0F [1 byte]` | uint8 |
| bare byte | raw single-byte value (no type tag) |
| `0x2B` | entity start marker (followed by `0x08 EntityTypeName 0x00`) |

#### Schema entries

Field names also appear as bare `0x08 FIELD_NAME 0x00` sequences **without** a preceding type tag earlier in the blob. These are schema declarations, not data-carrying fields. The `parse_tsaf()` function in `lib_djay.py` handles this distinction by checking for type tags before values.

#### Compact encoding

After the first occurrence of an entity type, subsequent instances use compact numeric field IDs (`0x05 FIELD_ID`). The `parse_tsaf()` function maintains a schema registry that maps entity type names to their field names from the first verbose occurrence, then uses this to decode compact entities.

The parser handles both encoding modes and returns a list of `TsafEntity` dataclasses with `type_name`, `fields` (dict of field names to values), and `compact` (bool) attributes.

### Automix cue points (`mediaItemUserData`)

Tracks where the DJ has configured automix transition points contain an `ADCCuePoint` entity with:

- **`automixStartPoint`** (`uint32`) — small integer (observed values 4–7), likely a grid position or beat count
- **`automixEndPoint`** (`uint32`) — same as above for the incoming side
- **`ADCCuePoint.time`** (`float32`, seconds) — the precise track position for the transition cue

The **time** field is what callers need — the integer automix points are djay's internal grid preferences, not actual time positions. The cue number byte (`0x2E` = 46 = automix-out, `0x2D` = 45 = automix-in) identifies which cue point is which.

The `mediaItemUserData` key is the same as the `localMediaItemLocations` key, so joining on key gives the Apple Music persistent ID.  See `load_automix_index()` in `lib_djay.py`.

> **Note**: When searching for a track in a fresh database export, the exact key may not match if the track was added/removed. Use `localMediaItemLocations` to find the correct key first, then query other collections by that key.

### historySessionItems

Each played track in a session is a `historySessionItems` row.  Relevant fields:

- `sessionUUID` (string) — links to the `historySessions` record
- `startTime` (float64 Core Data timestamp) — when this track started playing
- `duration` (float32, seconds) — track length
- `deckNumber` (uint8) — which deck (0-based)
- `originSourceID` (string, e.g. `com.apple.iTunes`) + Apple Music persistent ID in same blob

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
