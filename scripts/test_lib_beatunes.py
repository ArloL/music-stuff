from lib_beatunes import hex_id_to_beatunes_id, beatunes_id_to_hex_id


def test_hex_id_to_beatunes_id_high_bit_set():
    # "Never Said Goodbye" - hex has high bit set (B...)
    assert hex_id_to_beatunes_id("B1BB63F715E1025E") == 3583567841378501214


def test_hex_id_to_beatunes_id_high_bit_unset():
    # hex with high bit unset (0...) should produce negative beaTunes ID
    assert hex_id_to_beatunes_id("0575419A2E6CA0A4") < 0


def test_beatunes_id_to_hex_id_positive():
    assert beatunes_id_to_hex_id(3583567841378501214) == "B1BB63F715E1025E"


def test_beatunes_id_to_hex_id_negative():
    assert beatunes_id_to_hex_id(-8830079363858349404) == "0575419A2E6CA0A4"


def test_round_trip_from_hex():
    hex_id = "B1BB63F715E1025E"
    assert beatunes_id_to_hex_id(hex_id_to_beatunes_id(hex_id)) == hex_id


def test_round_trip_from_beatunes_id():
    beatunes_id = 3583567841378501214
    assert hex_id_to_beatunes_id(beatunes_id_to_hex_id(beatunes_id)) == beatunes_id


def test_hex_id_padded_to_16_chars():
    # Small beaTunes ID should still produce a zero-padded 16-char hex string
    result = beatunes_id_to_hex_id(0)
    assert len(result) == 16
    assert result == "8000000000000000"
