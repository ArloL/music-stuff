package io.github.arlol.beatunesdbviewer;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVPrinter;
import org.apache.commons.lang3.function.TriFunction;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import de.vandermeer.asciitable.AsciiTable;
import de.vandermeer.asciitable.CWC_LongestLine;

@SpringBootApplication
public class BeatunesDbviewerApplication implements ApplicationRunner {

	private static final Logger LOG = LoggerFactory
			.getLogger(BeatunesDbviewerApplication.class);
	public static final int BPM_TOLERANCE = 4;

	public static void main(String[] args) {
		SpringApplication.run(BeatunesDbviewerApplication.class, args);
	}

	@Autowired
	SongRepository songRepository;

	@Override
	public void run(ApplicationArguments args) throws Exception {

		LOG.info("{}", songRepository.findByNameContaining("Far Nearer"));
		LOG.info(
				"{}",
				songRepository
						.findAllPlayedSongsInPlaylist("Critical Mass Selection")
		);

		CSVFormat csvFormat = CSVFormat.DEFAULT.builder()
				.setHeader("song_id", "key", "bpm")
				.build();

		try (var writer = Files.newBufferedWriter(Path.of("songs.csv"));
				var printer = new CSVPrinter(writer, csvFormat)) {
			for (Song song : songRepository
					.findAllSongsInPlaylist("Critical Mass Selection")) {
				printer.printRecord(
						song.artist() + " - " + song.name(),
						song.tonalkey(),
						song.exactbpm()
				);
			}
		}

		var glokTimeOfNight = -2730468551274967094L;
		var dontEatTheHomies = 7045391083672295624L;
		var sunHarmonics = -1754864623550005176L;
		var moderatThisTime = -374389614597129505L;
		var surrender = 3019241645884347452L;
		var bonito = 1665329325033910003L;
		var buschtaxi = -6065868643012557817L;
		var peaceUNeed = 122020406781158675L;
		var littleRaver = 2911236038130032870L;
		var langsette = 2149715720658879404L;
		var yali = 6008492067627959237L;
		var xtc = 1325602142421953759L;
		var cantLeaveYou = -5751365970001065597L;
		var wohinWillstDu = 4466196167636350153L;
		var flowers = 566270618136868507L;
		var noSpace = -7750228720761693653L;
		var adoreU = -5362884256535021166L;
		var musicSoundsBetterWithYou = 3056537033641482349L;
		var bellaBooTrueRomance = 9183090035096810739L;
		var beeBear = -1980965085189031680L;

		var opal = -797837473343001362L;
		var glue = -4008632782404213503L;
		var raphaelSchoenEnergy = -4629189091379715702L;
		var affected = -1730534411063874573L;
		var waitedAllNight = -1197317593113363309L;
		var easyPrey = 2222844408585400916L;
		var flightfm = -195913331018806096L;
		var fiorucci = 8036272949323207712L;
		var unidos = -1124052115326879193L;
		var andromeda = 5085799661951493101L;
		var cantDoWithoutYou = -3257225827192527859L;
		var vajkoczy = -6065333829717269583L;

		var sleepSound = -2986607125485159918L;
		var wieSchoenDuBist = -2345412480785085071L;
		var keepMeInMyPlane = 2714070047318629720L;
		var bornSlippy = -2782899476190393637L;
		var brothers = -1274567764995009570L;
		var madeToStray = 7564155934685438451L;
		var painInTheAss = -8632984578091068324L;
		var sanProperItsHere = -8219592575606572857L;
		var smileItsANewDay = 6536447880061022166L;
		var leftBehind = 7877966654297912796L;
		var luvmaschine = 7032926356167753871L;
		var moving = -708107242740021751L;
		var everythingInItsRightPlace = 8181148944036896651L;
		var lonelyLover = 7147561003121904581L;
		var niceFirstSong = 9116139072803841255L;
		var galcherParlay = -3721484522009247387L;
		var galcherPutOn = -9222538084225020758L;
		var guyGerberWhatToDo = -7249254881768738465L;
		var ladyScience = 7914270736159500876L;
		var philippDolphia = 3460038468363839545L;
		var yamaha = 3364974199186770098L;
		var purpleDrank = 3463026062111012848L;
		var streetBeat = -57532306382113327L;
		var dorisburgEmotion = -8599961390070745305L;
		var bringTheSun = -404521654632970605L;
		var dianesLove = 5256697442091277020L;
		var ragysh = 8680761758092727633L;
		var butterflies = -8627883123988063491L;
		var seinfeldU = -6589484468724957098L;
		var dermot = -1019547102197982839L;
		var thankUAgain = 5040407027980190316L;
		var farNearer = -5934354521883931493L;

		var song = songRepository.findById(farNearer).orElseThrow();

		stayHere(songRepository::findRelevantSongsISelected, song);
	}

	private void stayHere(
			TriFunction<Double, Double, Collection<Integer>, Iterable<Song>> fun,
			Song seed
	) {
		var matching = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				MATCHING_KEYS.get(seed.tonalkey())
		);
		var boost = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_KEYS.get(seed.tonalkey())
		);
		var boostBoost = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_BOOST_KEYS.get(seed.tonalkey())
		);
		var boostBoostBoost = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_BOOST_BOOST_KEYS.get(seed.tonalkey())
		);
		var drop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_KEYS.get(seed.tonalkey())
		);
		var dropDrop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_DROP_KEYS.get(seed.tonalkey())
		);
		var dropDropDrop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_DROP_DROP_KEYS.get(seed.tonalkey())
		);
		var moodChange = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				MOOD_CHANGE_KEYS.get(seed.tonalkey())
		);
		System.out.println(print("Seed", List.of(seed)));
		System.out.println(print("Matching", matching));
		System.out.println(print("Boost", boost));
		System.out.println(print("Boost Boost", boostBoost));
		System.out.println(print("Boost Boost Boost", boostBoostBoost));
		System.out.println(print("Drop", drop));
		System.out.println(print("Drop Drop", dropDrop));
		System.out.println(print("Drop Drop Drop", dropDropDrop));
		System.out.println(print("Mood Change", moodChange));
	}

	private void whereToGo(
			TriFunction<Double, Double, Collection<Integer>, Iterable<Song>> fun,
			Song seed
	) {
		var matching = fun.apply(
				seed.exactbpm() + 0,
				seed.exactbpm() + BPM_TOLERANCE,
				MATCHING_KEYS.get(seed.tonalkey())
		);
		var boost = fun.apply(
				seed.exactbpm() + 0,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_KEYS.get(seed.tonalkey())
		);
		var boostBoost = fun.apply(
				seed.exactbpm() + 0,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_BOOST_KEYS.get(seed.tonalkey())
		);
		var boostBoostBoost = fun.apply(
				seed.exactbpm() + 0,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_BOOST_BOOST_KEYS.get(seed.tonalkey())
		);
		var drop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_KEYS.get(seed.tonalkey())
		);
		var dropDrop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_DROP_KEYS.get(seed.tonalkey())
		);
		var dropDropDrop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_DROP_DROP_KEYS.get(seed.tonalkey())
		);
		var moodChange = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				MOOD_CHANGE_KEYS.get(seed.tonalkey())
		);
		System.out.println(print("Seed", List.of(seed)));
		System.out.println(print("Matching", matching));
		System.out.println(print("Boost", boost));
		System.out.println(print("Boost Boost", boostBoost));
		System.out.println(print("Boost Boost Boost", boostBoostBoost));
		System.out.println(print("Drop", drop));
		System.out.println(print("Drop Drop", dropDrop));
		System.out.println(print("Drop Drop Drop", dropDropDrop));
		System.out.println(print("Mood Change", moodChange));
	}

	private void howToGetHere(
			TriFunction<Double, Double, Collection<Integer>, Iterable<Song>> fun,
			Song seed
	) {
		var matching = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				MATCHING_KEYS_REVERSE.get(seed.tonalkey())
		);
		var boost = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_KEYS_REVERSE.get(seed.tonalkey())
		);
		var boostBoost = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_BOOST_KEYS_REVERSE.get(seed.tonalkey())
		);
		var boostBoostBoost = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				BOOST_BOOST_BOOST_KEYS_REVERSE.get(seed.tonalkey())
		);
		var drop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_KEYS_REVERSE.get(seed.tonalkey())
		);
		var dropDrop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_DROP_KEYS_REVERSE.get(seed.tonalkey())
		);
		var dropDropDrop = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				DROP_DROP_DROP_KEYS_REVERSE.get(seed.tonalkey())
		);
		var moodChange = fun.apply(
				seed.exactbpm() - BPM_TOLERANCE,
				seed.exactbpm() + BPM_TOLERANCE,
				MOOD_CHANGE_KEYS_REVERSE.get(seed.tonalkey())
		);
		System.out.println(print("Seed", List.of(seed)));
		System.out.println(print("Matching", matching));
		System.out.println(print("Boost", boost));
		System.out.println(print("Boost Boost", boostBoost));
		System.out.println(print("Boost Boost Boost", boostBoostBoost));
		System.out.println(print("Drop", drop));
		System.out.println(print("Drop Drop", dropDrop));
		System.out.println(print("Drop Drop Drop", dropDropDrop));
		System.out.println(print("Mood Change", moodChange));
	}

	String print(String title, Iterable<Song> songs) {
		var sb = new StringBuilder("\n= " + title + " =\n");
		AsciiTable asciiTable = new AsciiTable();
		asciiTable.getRenderer().setCWC(new CWC_LongestLine());
		asciiTable.addRule();
		asciiTable.addRow("ID", "Artist", "Name", "BPM", "Key");
		asciiTable.addRule();
		for (var song : songs) {
			asciiTable.addRow(
					song.id(),
					song.artist(),
					song.name(),
					song.exactbpm(),
					song.tonalkey()
			);
			asciiTable.addRule();
		}
		return sb.append(asciiTable.render(120)).toString();
	}

	@SafeVarargs
	final <E> Collection<E> concat(Collection<E>... list) {
		return Arrays.stream(list).flatMap(Collection::stream).toList();
	}

	private static final Map<Integer, List<Integer>> MATCHING_KEYS = Map
			.ofEntries(
					Map.entry(11, List.of(11, 14)),
					Map.entry(13, List.of(13, 16)),
					Map.entry(15, List.of(15, 18)),
					Map.entry(17, List.of(17, 20)),
					Map.entry(19, List.of(19, 22)),
					Map.entry(21, List.of(21, 24)),
					Map.entry(23, List.of(23, 2)),
					Map.entry(1, List.of(1, 4)),
					Map.entry(3, List.of(3, 6)),
					Map.entry(5, List.of(5, 8)),
					Map.entry(7, List.of(7, 10)),
					Map.entry(9, List.of(9, 12)),
					Map.entry(12, List.of(12, 9)),
					Map.entry(14, List.of(14, 11)),
					Map.entry(16, List.of(16, 13)),
					Map.entry(18, List.of(18, 15)),
					Map.entry(20, List.of(20, 17)),
					Map.entry(22, List.of(22, 19)),
					Map.entry(24, List.of(24, 21)),
					Map.entry(2, List.of(2, 23)),
					Map.entry(4, List.of(4, 1)),
					Map.entry(6, List.of(6, 3)),
					Map.entry(8, List.of(8, 5)),
					Map.entry(10, List.of(10, 7))
			);
	private static final Map<Integer, List<Integer>> MATCHING_KEYS_REVERSE = reverse(
			MATCHING_KEYS
	);

	private static final Map<Integer, List<Integer>> BOOST_KEYS = Map.ofEntries(
			Map.entry(11, List.of(13)),
			Map.entry(13, List.of(15)),
			Map.entry(15, List.of(17)),
			Map.entry(17, List.of(19)),
			Map.entry(19, List.of(21)),
			Map.entry(21, List.of(23)),
			Map.entry(23, List.of(1)),
			Map.entry(1, List.of(3)),
			Map.entry(3, List.of(5)),
			Map.entry(5, List.of(7)),
			Map.entry(7, List.of(9)),
			Map.entry(9, List.of(11)),
			Map.entry(12, List.of(11, 14)),
			Map.entry(14, List.of(13, 16)),
			Map.entry(16, List.of(15, 18)),
			Map.entry(18, List.of(17, 20)),
			Map.entry(20, List.of(19, 22)),
			Map.entry(22, List.of(21, 24)),
			Map.entry(24, List.of(23, 2)),
			Map.entry(2, List.of(1, 4)),
			Map.entry(4, List.of(3, 6)),
			Map.entry(6, List.of(5, 8)),
			Map.entry(8, List.of(7, 10)),
			Map.entry(10, List.of(9, 12))
	);
	private static final Map<Integer, List<Integer>> BOOST_KEYS_REVERSE = reverse(
			BOOST_KEYS
	);

	private static final Map<Integer, List<Integer>> BOOST_BOOST_KEYS = Map
			.ofEntries(
					Map.entry(11, List.of(5)),
					Map.entry(13, List.of(7)),
					Map.entry(15, List.of(9)),
					Map.entry(17, List.of(11)),
					Map.entry(19, List.of(13)),
					Map.entry(21, List.of(15)),
					Map.entry(23, List.of(17)),
					Map.entry(1, List.of(19)),
					Map.entry(3, List.of(21)),
					Map.entry(5, List.of(23)),
					Map.entry(7, List.of(1)),
					Map.entry(9, List.of(3)),
					Map.entry(12, List.of(6)),
					Map.entry(14, List.of(8)),
					Map.entry(16, List.of(10)),
					Map.entry(18, List.of(12)),
					Map.entry(20, List.of(14)),
					Map.entry(22, List.of(16)),
					Map.entry(24, List.of(18)),
					Map.entry(2, List.of(20)),
					Map.entry(4, List.of(22)),
					Map.entry(6, List.of(24)),
					Map.entry(8, List.of(2)),
					Map.entry(10, List.of(4))
			);
	private static final Map<Integer, List<Integer>> BOOST_BOOST_KEYS_REVERSE = reverse(
			BOOST_BOOST_KEYS
	);

	private static final Map<Integer, List<Integer>> BOOST_BOOST_BOOST_KEYS = Map
			.ofEntries(
					Map.entry(11, List.of(15, 1)),
					Map.entry(13, List.of(17, 3)),
					Map.entry(15, List.of(19, 5)),
					Map.entry(17, List.of(21, 7)),
					Map.entry(19, List.of(23, 9)),
					Map.entry(21, List.of(1, 11)),
					Map.entry(23, List.of(3, 13)),
					Map.entry(1, List.of(5, 15)),
					Map.entry(3, List.of(7, 17)),
					Map.entry(5, List.of(9, 19)),
					Map.entry(7, List.of(11, 21)),
					Map.entry(9, List.of(13, 23)),
					Map.entry(12, List.of(16, 2)),
					Map.entry(14, List.of(18, 4)),
					Map.entry(16, List.of(20, 6)),
					Map.entry(18, List.of(22, 8)),
					Map.entry(20, List.of(24, 10)),
					Map.entry(22, List.of(2, 12)),
					Map.entry(24, List.of(4, 14)),
					Map.entry(2, List.of(6, 16)),
					Map.entry(4, List.of(8, 18)),
					Map.entry(6, List.of(10, 20)),
					Map.entry(8, List.of(12, 22)),
					Map.entry(10, List.of(14, 24))
			);
	private static final Map<Integer, List<Integer>> BOOST_BOOST_BOOST_KEYS_REVERSE = reverse(
			BOOST_BOOST_BOOST_KEYS
	);

	private static final Map<Integer, List<Integer>> DROP_KEYS = Map.ofEntries(
			Map.entry(11, List.of(12, 9)),
			Map.entry(13, List.of(14, 11)),
			Map.entry(15, List.of(16, 13)),
			Map.entry(17, List.of(18, 15)),
			Map.entry(19, List.of(20, 17)),
			Map.entry(21, List.of(22, 19)),
			Map.entry(23, List.of(24, 21)),
			Map.entry(1, List.of(2, 23)),
			Map.entry(3, List.of(4, 1)),
			Map.entry(5, List.of(6, 3)),
			Map.entry(7, List.of(8, 5)),
			Map.entry(9, List.of(10, 7)),
			Map.entry(12, List.of(10)),
			Map.entry(14, List.of(12)),
			Map.entry(16, List.of(14)),
			Map.entry(18, List.of(16)),
			Map.entry(20, List.of(18)),
			Map.entry(22, List.of(20)),
			Map.entry(24, List.of(22)),
			Map.entry(2, List.of(24)),
			Map.entry(4, List.of(2)),
			Map.entry(6, List.of(4)),
			Map.entry(8, List.of(6)),
			Map.entry(10, List.of(8))
	);
	private static final Map<Integer, List<Integer>> DROP_KEYS_REVERSE = reverse(
			DROP_KEYS
	);

	private static final Map<Integer, List<Integer>> DROP_DROP_KEYS = Map
			.ofEntries(
					Map.entry(11, List.of(17)),
					Map.entry(13, List.of(19)),
					Map.entry(15, List.of(21)),
					Map.entry(17, List.of(23)),
					Map.entry(19, List.of(1)),
					Map.entry(21, List.of(3)),
					Map.entry(23, List.of(5)),
					Map.entry(1, List.of(7)),
					Map.entry(3, List.of(9)),
					Map.entry(5, List.of(11)),
					Map.entry(7, List.of(13)),
					Map.entry(9, List.of(15)),
					Map.entry(12, List.of(18)),
					Map.entry(14, List.of(20)),
					Map.entry(16, List.of(22)),
					Map.entry(18, List.of(24)),
					Map.entry(20, List.of(2)),
					Map.entry(22, List.of(4)),
					Map.entry(24, List.of(6)),
					Map.entry(2, List.of(8)),
					Map.entry(4, List.of(10)),
					Map.entry(6, List.of(12)),
					Map.entry(8, List.of(14)),
					Map.entry(10, List.of(16))
			);
	private static final Map<Integer, List<Integer>> DROP_DROP_KEYS_REVERSE = reverse(
			DROP_DROP_KEYS
	);

	private static final Map<Integer, List<Integer>> DROP_DROP_DROP_KEYS = Map
			.ofEntries(
					Map.entry(11, List.of(7)),
					Map.entry(13, List.of(9)),
					Map.entry(15, List.of(11)),
					Map.entry(17, List.of(13)),
					Map.entry(19, List.of(15)),
					Map.entry(21, List.of(17)),
					Map.entry(23, List.of(19)),
					Map.entry(1, List.of(21)),
					Map.entry(3, List.of(23)),
					Map.entry(5, List.of(1)),
					Map.entry(7, List.of(3)),
					Map.entry(9, List.of(5)),
					Map.entry(12, List.of(8)),
					Map.entry(14, List.of(10)),
					Map.entry(16, List.of(12)),
					Map.entry(18, List.of(14)),
					Map.entry(20, List.of(16)),
					Map.entry(22, List.of(18)),
					Map.entry(24, List.of(20)),
					Map.entry(2, List.of(22)),
					Map.entry(4, List.of(24)),
					Map.entry(6, List.of(2)),
					Map.entry(8, List.of(4)),
					Map.entry(10, List.of(6))
			);
	private static final Map<Integer, List<Integer>> DROP_DROP_DROP_KEYS_REVERSE = reverse(
			DROP_DROP_DROP_KEYS
	);

	private static final Map<Integer, List<Integer>> MOOD_CHANGE_KEYS = Map
			.ofEntries(
					Map.entry(11, List.of(6)),
					Map.entry(13, List.of(8)),
					Map.entry(15, List.of(10)),
					Map.entry(17, List.of(12)),
					Map.entry(19, List.of(14)),
					Map.entry(21, List.of(16)),
					Map.entry(23, List.of(18)),
					Map.entry(1, List.of(20)),
					Map.entry(3, List.of(22)),
					Map.entry(5, List.of(24)),
					Map.entry(7, List.of(2)),
					Map.entry(9, List.of(4)),
					Map.entry(12, List.of(17)),
					Map.entry(14, List.of(19)),
					Map.entry(16, List.of(21)),
					Map.entry(18, List.of(23)),
					Map.entry(20, List.of(1)),
					Map.entry(22, List.of(3)),
					Map.entry(24, List.of(5)),
					Map.entry(2, List.of(7)),
					Map.entry(4, List.of(9)),
					Map.entry(6, List.of(11)),
					Map.entry(8, List.of(13)),
					Map.entry(10, List.of(15))
			);
	private static final Map<Integer, List<Integer>> MOOD_CHANGE_KEYS_REVERSE = reverse(
			MOOD_CHANGE_KEYS
	);

	Collection<Integer> getMatchingTonalKeys(Song song) {
		if (song.tonalkey() % 2 == 1) {
			return List.of(song.tonalkey(), rangeCheck(song.tonalkey() + 3));
		} else {
			return List.of(song.tonalkey(), rangeCheck(song.tonalkey() - 3));
		}
	}

	Collection<Integer> getBoostTonalKeys(Song song) {
		if (song.tonalkey() % 2 == 1) {
			return List.of(rangeCheck(song.tonalkey() + 2));
		} else {
			return List.of(
					rangeCheck(song.tonalkey() - 1),
					rangeCheck(song.tonalkey() + 2)
			);
		}
	}

	Collection<Integer> getBoostBoostTonalKeys(Song song) {
		return List.of(rangeCheck(song.tonalkey() - 6));
	}

	Collection<Integer> getBoostBoostBoostTonalKeys(Song song) {
		return List.of(
				rangeCheck(song.tonalkey() + 4),
				rangeCheck(song.tonalkey() - 10)
		);
	}

	Collection<Integer> getDropTonalKeys(Song song) {
		if (song.tonalkey() % 2 == 1) {
			return List.of(
					rangeCheck(song.tonalkey() + 1),
					rangeCheck(song.tonalkey() - 2)
			);
		} else {
			return List.of(rangeCheck(song.tonalkey() - 2));
		}
	}

	Collection<Integer> getDropDropTonalKeys(Song song) {
		return List.of(rangeCheck(song.tonalkey() + 6));
	}

	Collection<Integer> getDropDropDropTonalKeys(Song song) {
		return List.of(rangeCheck(song.tonalkey() - 4));
	}

	Collection<Integer> getMoodChangeTonalKeys(Song song) {
		if (song.tonalkey() % 2 == 1) {
			return List.of(rangeCheck(song.tonalkey() - 5));
		} else {
			return List.of(rangeCheck(song.tonalkey() + 5));
		}
	}

	private static <E> Map<E, List<E>> reverse(Map<E, List<E>> map) {
		var result = new HashMap<E, List<E>>();
		map.forEach((target, sources) -> {
			for (E source : sources) {
				result.computeIfAbsent(source, _ -> new ArrayList<>())
						.add(target);
			}
		});
		return result;
	}

	int rangeCheck(int key) {
		if (key < 1) {
			return key + 24;
		}
		if (key > 24) {
			return key - 24;
		}
		return key;
	}

}
