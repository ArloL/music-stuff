package io.github.arlol.beatunesdbviewer;

import java.util.Collection;

import org.springframework.data.jdbc.repository.query.Query;
import org.springframework.data.repository.CrudRepository;

public interface SongRepository extends CrudRepository<Song, Long> {

	Iterable<Song> findByNameContaining(String name);

	@Query("""
			SELECT * FROM SONGS s
			WHERE
			GENRE IN ('Electronic', 'Ambient')
			AND RATING >= 80
			AND RATINGCOMPUTED = FALSE
			AND COMMENTS != 'ignore'
			AND COMMENTS NOT LIKE '%mixed%'
			AND EXACTBPM BETWEEN :fromBpm and :toBpm
			AND TONALKEY IN (:tonalKeys)
			ORDER BY RATING DESC, EXACTBPM ASC
			""")
	Iterable<Song> findRelevantSongs(
			double fromBpm,
			double toBpm,
			Collection<Integer> tonalKeys
	);

	@Query("""
			SELECT s.* FROM PLAYLISTS_SONGS ps
			LEFT JOIN SONGS s ON ps.PLAYLISTITEMS_ID = s.ID
			LEFT JOIN PLAYLISTS p ON p.ID = ps.PLAYLISTS_ID
			WHERE
			p.NAME = :name
			AND s.COMMENTS != 'ignore'
			AND s.COMMENTS NOT LIKE '%mixed%'
			ORDER BY ps.INDEXCOLUMN
			""")
	Iterable<Song> findAllSongsInPlaylist(String name);

	@Query(
		"""
				SELECT * FROM SONGS s
				WHERE
				ID IN (SELECT PLAYLISTITEMS_ID FROM PLAYLISTS_SONGS ps LEFT JOIN PLAYLISTS p ON p.ID = ps.PLAYLISTS_ID WHERE p.NAME = :name)
				AND ID IN (SELECT PLAYLISTITEMS_ID FROM PLAYLISTS_SONGS ps LEFT JOIN PLAYLISTS p ON p.ID = ps.PLAYLISTS_ID WHERE p.NAME = 'Critical Mass Played')
				AND GENRE IN ('Electronic', 'Ambient')
				AND RATING >= 80
				AND RATINGCOMPUTED = FALSE
				AND COMMENTS != 'ignore'
				AND COMMENTS NOT LIKE '%mixed%'
				ORDER BY s.NAME ASC
				"""
	)
	Iterable<Song> findAllPlayedSongsInPlaylist(String name);

	@Query(
		"""
				SELECT * FROM SONGS s
				WHERE
				ID NOT IN (SELECT PLAYLISTITEMS_ID FROM PLAYLISTS_SONGS ps LEFT JOIN PLAYLISTS p ON p.ID = ps.PLAYLISTS_ID WHERE p.NAME = 'Critical Mass Played')
				AND GENRE IN ('Electronic', 'Ambient')
				AND RATING >= 80
				AND RATINGCOMPUTED = FALSE
				AND COMMENTS != 'ignore'
				AND COMMENTS NOT LIKE '%mixed%'
				AND EXACTBPM BETWEEN :fromBpm and :toBpm
				AND TONALKEY IN (:tonalKeys)
				ORDER BY RATING DESC, EXACTBPM ASC
				"""
	)
	Iterable<Song> findRelevantSongsINeverPlayed(
			double fromBpm,
			double toBpm,
			Collection<Integer> tonalKeys
	);

	@Query(
		"""
				SELECT * FROM SONGS s
				WHERE
				ID  IN (SELECT PLAYLISTITEMS_ID FROM PLAYLISTS_SONGS ps LEFT JOIN PLAYLISTS p ON p.ID = ps.PLAYLISTS_ID WHERE p.NAME = 'Would Play')
				AND GENRE IN ('Electronic', 'Ambient')
				AND RATING >= 80
				AND RATINGCOMPUTED = FALSE
				AND COMMENTS != 'ignore'
				AND COMMENTS NOT LIKE '%mixed%'
				AND EXACTBPM BETWEEN :fromBpm and :toBpm
				AND TONALKEY IN (:tonalKeys)
				ORDER BY RATING DESC, EXACTBPM ASC
				"""
	)
	Iterable<Song> findRelevantSongsISelected(
			double fromBpm,
			double toBpm,
			Collection<Integer> tonalKeys
	);

	@Query(
		"""
				SELECT * FROM SONGS s
				WHERE
				ID NOT IN (SELECT PLAYLISTITEMS_ID FROM PLAYLISTS_SONGS ps LEFT JOIN PLAYLISTS p ON p.ID = ps.PLAYLISTS_ID WHERE p.NAME = 'Critical Mass Played')
				AND ID IN (SELECT PLAYLISTITEMS_ID FROM PLAYLISTS_SONGS ps LEFT JOIN PLAYLISTS p ON p.ID = ps.PLAYLISTS_ID WHERE p.NAME = 'Would Play')
				AND GENRE IN ('Electronic', 'Ambient')
				AND RATING >= 80
				AND RATINGCOMPUTED = FALSE
				AND COMMENTS != 'ignore'
				AND COMMENTS NOT LIKE '%mixed%'
				AND EXACTBPM BETWEEN :fromBpm and :toBpm
				AND TONALKEY IN (:tonalKeys)
				ORDER BY RATING DESC, EXACTBPM ASC
				"""
	)
	Iterable<Song> findRelevantSongsISelectedAndNeverPlayed(
			double fromBpm,
			double toBpm,
			Collection<Integer> tonalKeys
	);

}
