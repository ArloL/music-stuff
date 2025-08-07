package io.github.arlol.beatunesdbviewer;

import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Table;

@Table("SONGS")
public record Song(
		@Id Long id,
		String artist,
		String name,
		String comments,
		Double exactbpm,
		Integer tonalkey,
		Integer rating
) {

}
