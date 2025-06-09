from bluprints import build_desc
from bs4 import BeautifulSoup
from duppy import NEGATIVE_MESSAGES, produce_report
from pathlib import Path
from requests.exceptions import HTTPError
from rich import print as rprint
from rich import print_json
from rich.logging import RichHandler
from rich.text import Text
from typing import cast, Type, TypeVar
import argparse
import breppy
import logging
import msgspec
import os
import platformdirs
import re
import sys
import tomlkit

logging.basicConfig(
	level=logging.INFO, format='%(message)s', datefmt='[%X]', handlers=[RichHandler()]
)
PLATFORMDIRS = platformdirs.PlatformDirs(appname='torpost', appauthor=False)
CONFIG_FOLDER = PLATFORMDIRS.user_config_path
DEFAULT_CONFIGURATION_PATH = CONFIG_FOLDER / 'torpost_config.toml'
DEFAULT_ENCODING = 'utf-8'
T = TypeVar('T')
ERROR_MESSAGES = [
	"Your torrent has been uploaded however, because you didn't choose the private option you must download the torrent file from here before you can start seeding.",
	'Wrong authorization key, please go back and try again.',
]


class ConfigError(Exception):
	pass


class Style(msgspec.Struct, kw_only=True):
	open: str = '[align=center][color=#FFFFFF][font=Quantico][size=6][br][br][b]{TITLE}[/b][br][br][img]{COVER}[/img]'
	poster: str = '[br][br]{POSTER}'
	info: str = '[br][br][table=nball,center,92%][tr][td=center,center,nball][b][bg=transparent,94%]{DESC}[br][/bg][/b][/td][/tr][/table][/size]'
	video_stats: str = '[size=4][br][br][color=#ffffff]Video Length Distribution (95th)[/color][/size][br]{GRAPH}[br][br][size=2][color=#FFFF][table=100%,#222222][tr][td][u][b][align=left]Nudity Level[/align][/b][/u][/td][td][align=left][b]{NUDITY}[/b][/align][/td][/tr][tr][td][u][b][align=left]Images Context[/align][/b][/u][/td][td][align=left][b]{IMAGES_CONTEXT}[/b][/align][/td][/tr][tr][td][u][b][align=left]Extras[/align][/b][/u][/td][td][align=left]{EXTRAS}[/align][/td][/tr][tr][td][u][b][align=left]Maximum Length[/align][/b][/u][align=right]hh:mm:ss[/align][/td][td][b]{MAXIMUM}[/b][/td][/tr][tr][td][u][b][align=left]Minimum Length[/align][/b][/u][align=right]hh:mm:ss[/align][/td][td][b]{MINIMUM}[/b][/td][/tr][tr][td][u][b][align=left]Average Length[/align][/b][/u][align=right]hh:mm:ss[/align][/td][td][b]{AVERAGE}[/b][/td][/tr][tr][td][u][b][align=left]Median Length[/align][/b][/u][align=right]hh:mm:ss[/align][/td][td][b]{MEDIAN}[/b][/td][/tr][tr][td][u][b][align=left]Total Length[/align][/b][/u][align=right]hh:mm:ss[/align][/td][td][b]{SUM}[/b][/td][/tr][/table][/color][/size][br]'
	collage: str = '[size=6][br][br][spoiler=Pictures]{COLLAGES}[/spoiler][br][/size]'
	screens: str = '[size=6][br][spoiler=Screenshots]{SCREENS}[/spoiler][/size]'
	close: str = '[/font][/color][/align]'


class Styles(msgspec.Struct, kw_only=True):
	default: dict[str, Style] = msgspec.field(default_factory=dict)


CATEGORIES = {
	'Emp': {
		'Amateur': 1,
		'Anal': 2,
		'Asian': 5,
		'BBW': 6,
		'BDSM': 30,
		'Big Ass': 36,
		'Big Tits': 8,
		'Black': 7,
		'Classic': 9,
		'Creampie': 37,
		'Cumshot': 10,
		'Fetish': 12,
		'Gang Bang / Orgy': 14,
		'Gay / Bi': 39,
		'Hairy': 56,
		'Hardcore': 35,
		'Hentai / 3D': 3,
		'Homemade': 25,
		'Interracial': 43,
		'Latina': 16,
		'Lesbian': 23,
		'Lingerie': 52,
		'Magazines': 27,
		'Manga / Comic': 53,
		'Masturbation': 18,
		'Mature': 26,
		'Megapack': 40,
		'Natural Tits': 41,
		'Oral': 17,
		'Other': 29,
		'Parody': 47,
		'Pictures / Images': 21,
		'Piss': 50,
		'Porn Music Videos': 55,
		'Pregnant / Preggo': 46,
		'Scat/Puke': 51,
		'Siterip': 22,
		'Softcore': 20,
		'Squirt': 49,
		'Straight': 34,
		'Teen': 19,
		'Transgender': 15,
		'Voyeur': 45,
		'XXX Games / Apps': 13,
	},
	'Ent': {'FemDom': 1, 'LezDom': 2, 'POV': 4, 'Scat': 5, 'TransDom': 3},
	'Pbay': {
		'Amateur': 1,
		'Anal': 2,
		'Asian': 3,
		'BBW': 4,
		'BDSM': 31,
		'Black': 5,
		'Blowjob': 6,
		'Busty': 7,
		'Classic': 32,
		'Creampie': 9,
		'Fetish': 12,
		'Gay&Bi': 15,
		'Gonzo': 16,
		'Hentai': 19,
		'Homemade': 30,
		'Interracial': 20,
		'Latin': 21,
		'Lesbian': 22,
		'Mature': 23,
		'Megapack': 47,
		'Old + Young': 49,
		'Orgy': 24,
		'Other': 25,
		'Pics': 26,
		'POV': 50,
		'Sick': 27,
		'Site rips': 35,
		'Solo': 48,
		'Straight': 28,
		'Teen': 29,
		'Transsexual': 33,
		'VR Porn': 51,
	},
}


class DefaultConfig(msgspec.Struct, kw_only=True):
	styles: dict[str, Style] = msgspec.field(
		default_factory=lambda: {'default': Style()}
	)
	desc_path: Path = CONFIG_FOLDER / 'desc'
	torrents_path: Path = CONFIG_FOLDER / 'torrents'


def encode_hook(obj: Path | str) -> str:
	if isinstance(obj, Path):
		return str(obj)

	return obj


def decode_hook(type_: Type[Path], value: Path | str) -> Path | str:
	if type_ is Path and isinstance(value, str):
		return Path(value)

	return value


def get_config_path(path: Path | None = None) -> Path:
	if path is None:
		return DEFAULT_CONFIGURATION_PATH

	return Path(path).resolve()


def load_config(path: Path | None = None) -> DefaultConfig:
	path = get_config_path(path)

	with open(path, 'r', encoding=DEFAULT_ENCODING) as fp:
		data = fp.read()

	return msgspec.toml.decode(data, type=DefaultConfig, dec_hook=decode_hook)


def save_config(configuration: DefaultConfig, path: Path | None = None) -> None:
	path = get_config_path(path)
	data = tomlkit.dumps(msgspec.to_builtins(configuration, enc_hook=encode_hook))
	path.parent.mkdir(parents=True, exist_ok=True)

	with open(path, 'w', encoding=DEFAULT_ENCODING) as fp:
		fp.write(data)

	logging.info(f'New default config saved in: {DEFAULT_CONFIGURATION_PATH}')


def load_or_create_config(path: Path | None = None) -> DefaultConfig:
	path = get_config_path(path)

	if path.exists():
		logging.info(f'Previous config found in: {DEFAULT_CONFIGURATION_PATH}')

	try:
		return load_config(path)

	except FileNotFoundError:
		pass

	configuration = DefaultConfig()
	save_config(configuration, path)

	return configuration


CONFIG = load_or_create_config()
STYLES = CONFIG.styles


def parse_torpost() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(prog='torpost')
	parser.add_argument('filepath', nargs='+', help='Filepath to tag_file')
	parser.add_argument(
		'--collage',
		'-c',
		nargs='+',
		type=valid_collage,
		help='Add to a collage after upload',  #make it accept lower and upper collages regardless
	)
	parser.add_argument('--no-prompts', '-n', action='store_true', help='')
	parser.add_argument(
		'--tracker',
		'-t',
		nargs='+',
		choices=['Emp', 'Ent', 'PBay'],
		help='Trackers on which torrents will be posted',
	)

	return parser


def valid_collage(value: str) -> str:
	str_pattern = '^(Emp|Ent|PBay)-\\d{4}$'
	raw_regex = r'' + str_pattern
	collage_pattern = re.compile(raw_regex)

	if not collage_pattern.match(value):
		raise argparse.ArgumentTypeError(
			'Invalid --collage format. Must start with Emp | Ent | PBay, followed by a dash and a four-digit number.'
		)

	return value


def make_bbcode(
	desc_path: Path, desc: dict[str, str | dict[str, str]], style: str
) -> tuple[str, list[str]]:
	bbcode = []
	theme = STYLES[style]

	try:
		theme = STYLES[style]

	except (AttributeError, KeyError, ValueError) as e:
		logging.error(f'{type(e).__name__}: {e}')
		logging.shutdown()
		sys.exit(1)

	if isinstance(desc['Title'], str) and isinstance(desc['Cover'], str):
		bbcode.append(
			theme.open.replace(
				'{TITLE}', desc['Title'].replace(' {CamWhorders}', '')
			).replace('{COVER}', desc['Cover'])
		)

	if desc.get('Poster') and isinstance(desc.get('Poster'), str):
		bbcode.append(theme.poster.replace('{POSTER}', desc['Poster']))

	text = []
	subkeys = (
		'File',
		'Studio',
		'Resolution',
		'Qualifier',
		'Performer',
		'Action',
		'Body',
		'Ethnic',
		'Nation',
		'Costume',
		'Position',
		'Plot',
		'Location',
		'Date',
		'Comment',
	)

	for key in subkeys:
		if key in desc:
			value = desc[key] if desc[key] else None

			if isinstance(value, str):
				text.append(value) 

	joined_text = '[br][br]'.join(text)
	bbcode.append(theme.info.replace('{DESC}', joined_text))

	if 'Graph' in desc:
		if isinstance(desc['Table'], dict):
			table: dict[str, str] = desc['Table']

			if isinstance(desc['Graph'], str):
				bbcode.append(
					theme.video_stats.replace('{GRAPH}', desc['Graph'])
					.replace('{NUDITY}', table['Nudity'])
					.replace('{IMAGES_CONTEXT}', desc['Table']['Images'])
					.replace('{EXTRAS}', desc['Table']['Extras'])
					.replace('{MAXIMUM}', desc['Table']['Maximum'])
					.replace('{MINIMUM}', desc['Table']['Minimum'])
					.replace('{AVERAGE}', desc['Table']['Average'])
					.replace('{MEDIAN}', desc['Table']['Median'])
					.replace('{SUM}', desc['Table']['Total'])
				)

	if 'Collages' in desc:
		if isinstance(desc['Collages'], str):
			bbcode.append(theme.collage.replace('{COLLAGES}', desc['Collages']))#list[str]??

	if 'Screens' in desc:
		if isinstance(desc['Screens'], str):
			bbcode.append(theme.screens.replace('{SCREENS}', desc['Screens']))#list[str]??

	bbcode.append(theme.close)
	final_bbcode = ('[br][br]').join(bbcode)

	with open(desc_path, 'w') as desc_file:
		desc_file.write(final_bbcode)

	return final_bbcode, text


def preview_desc(desc: dict[str, str | dict[str, str]], text: list[str]) -> Text:
	preview = []
	preview.append(f'Title:{os.linesep}{desc["Title"]}')
	preview.append(f'Cover:{os.linesep}{desc["Cover"]}')
	preview.append(f'Taglist:{os.linesep}{desc["Taglist"]}')
	preview.append(f'Desc:')
	preview.append(f'{os.linesep * 2}'.join(text))

	if 'Poster' in desc:
		preview.append(f'Poster:{os.linesep}{desc["Poster"]}')

	if 'Graph' in desc:
		preview.append(f'Graph:{os.linesep}{desc["Graph"]}')

	else:
		preview.append(f'Graph: NULL')

	if 'Table' in desc:
		table = desc['Table']

		if isinstance(table, dict):
			if 'Maximum' in table:
				maximum = table['Maximum']

				if isinstance(maximum, str):
					preview.append(f'Maximum: {maximum}')

			else:
				preview.append(f'Maximum: NULL')

			if 'Minimum' in table:
				minimum = table['Minimum']

				if isinstance(minimum, str):
					preview.append(f'Minimum: {minimum}')

			else:
				preview.append(f'Minimum: NULL')

			if 'Average' in table:
				average = table['Average']

				if isinstance(average, str):
					preview.append(f'Average: {average}')

			else:
				preview.append(f'Average: NULL')

			if 'Median' in table:
				median = table['Median']

				if isinstance(median, str):
					preview.append(f'Median: {median}')

			else:
				preview.append(f'Median: NULL')

			if 'Total' in table:
				total = table['Total']

				if isinstance(total, str):
					preview.append(f'Total: {total}')

			else:
				preview.append(f'Total: NULL')

			if 'Images' in table:
				images = table['Images']

				if isinstance(images, str):
					preview.append(f'Images: {images}')

			else:
				preview.append(f'Images: NULL')

			if 'Extras' in table:
				extras = table['Extras']

				if isinstance(extras, str):
					preview.append(f'Extras: {extras}')

			else:
				preview.append(f'Extras: NULL')

	if 'Collages' in desc:
		preview.append(f'Collages:{os.linesep}{desc["Collages"]}')

	else:
		preview.append(f'Collages: NULL')

	if 'Screens' in desc:
		preview.append(f'Screens:{os.linesep}{desc["Screens"]}')

	else:
		preview.append(f'Screens: NULL')

	return Text(f'{os.linesep * 2}'.join(preview), justify='center', style='bold')


def post_torrent(
	bbcode: str,
	desc: dict[str, str | dict[str, str]],
	name: str,
	tracker: str,
	collages: list[str] | None = None,
	no_prompts: bool = False,
) -> None:
	categories_dict = cast(dict[str, str], desc['Category'])
	chosen_category = categories_dict[tracker]

	if isinstance(chosen_category, str):
		category = CATEGORIES[tracker][chosen_category]

	torrent = CONFIG.torrents_path / f'[{tracker}] {name}.torrent'

	while not torrent.exists():
		torrent = Path(
			input(f'The path {torrent} is invalid, please provide path.{os.linesep}')
		)

	try:
		if isinstance(chosen_category, str):
			category = CATEGORIES[tracker][chosen_category]
			torrent = CONFIG.torrents_path / f'[{tracker}] {name}.torrent'

			while not torrent.exists():
				torrent = Path(
					input(
						f'The path {torrent} is invalid, please provide path.{os.linesep}'
					)
				)

		r1 = breppy.build(torrent, tracker)
		r1.raise_for_status

	except (AttributeError, HTTPError, TypeError) as e:
		logging.error(f'{type(e).__name__}: {e}')
		logging.shutdown()
		sys.exit(1)

	logging.info(f'Filename: {os.path.basename(torrent)}')
	logging.info(f'Tracker: {tracker}')
	dupecheck = msgspec.to_builtins(
		next(produce_report(torrent, tracker, r1, True, True))
	)
	print_json(data=dupecheck)
	choice = ''

	if no_prompts:
		choice = 'no'

	if isinstance(dupecheck['Percentage'], float):
		percentage = dupecheck['Percentage']
	else:
		percentage = -0.01

	message_bar = dupecheck['MessageBar'] if 'MessageBar' in dupecheck else ''

	if 50.00 <= percentage <= 100.00:
		logging.warning(
			f'Percentage of duped content is {percentage}%, are you sure you still want to upload? (yes/no){os.linesep}'
		)

		while choice.lower() not in ['yes', 'y', 'no', 'n']:
			choice = input()

	if (
		00.00 <= percentage <= 49.99
		or choice in ['yes', 'y']
		or message_bar == NEGATIVE_MESSAGES[0]
	):
		if 00.00 <= percentage <= 49.99:
			logging.info(
				f'Percentage of duped content is {percentage}%, approved for uploading.'
			)

		if choice == 'yes':
			logging.warning('Dupe detection bypassed.')

		logging.info('STATUS: READY TO UPLOAD')

		if not no_prompts:
			input(f'{os.linesep}Press Enter to continue{os.linesep}')

		try:
			if (
				isinstance(desc['Cover'], str)
				and isinstance(desc['Taglist'], str)
				and isinstance(desc['Title'], str)
			):
				cover = desc['Cover']
				taglist = desc['Taglist']
				title = desc['Title']
				payload = breppy.prepare_upload(
					bbcode, category, cover, taglist, title, tracker
				)
				r2 = breppy.build(torrent, tracker, payload)
				r2.raise_for_status

				if r2.status_code == 200 and 'torrents.php?id=' not in r2.url:
					logging.error(
						'Request was successful but the upload was not finalized.'
					)
					upload_soup = BeautifulSoup(r2.content, 'html.parser')
					message_bar_element = upload_soup.find(id='messagebar')

					if message_bar_element:
						message = message_bar_element.text
						logging.error(f'MessageBarError: {message}')

					elif ERROR_MESSAGES[1] in r2.text:
						logging.error(ERROR_MESSAGES[1])

					elif ERROR_MESSAGES[0] in r2.text:
						logging.warning(
							ERROR_MESSAGES[0]
						)
						url = upload_soup.find(
							'a', href=lambda href: href and 'torrents.php?id=' in href
						)

					with open(f'req-{name}-{tracker}.html', 'wb') as debug_file:
						debug_file.write(r2.content)

					logging.info(
						'Request was saved for debugging in the current working directory.'
					)

					if collages and not ERROR_MESSAGES[0] in r2.text:
						logging.error(
							'Torrent was not added to collage(s) because the upload was not finalized.'
						)

				if r2.status_code == 200 and (
					'torrents.php?id=' in r2.url or ERROR_MESSAGES[0] in r2.text
				):
					logging.info('Torrent successfully uploaded')

					if 'torrents.php?id=' in r2.url:
						logging.info(r2.url)

					if ERROR_MESSAGES[0] in r2.text:
						logging.info(url)

					if collages:
						for c in collages:
							cl = int(c.split('-')[1])

							match tracker:
								case 'Emp' | 'Ent':
									collage_req = breppy.collage(cl, r2.url, tracker)

								case 'PBay':
									collage_req = breppy.legacy_collage(
										cl, r2.url, tracker
									)

							collage_req.raise_for_status

							if collage_req.status_code == 200:
								logging.info(
									f'{os.linesep}Torrent successfully added to collage'
								)
								soup = BeautifulSoup(collage_req.content, 'html.parser')

								if soup.title:
									title = ' '.join(soup.title.text.split())

									logging.info(title)
									logging.info(c)
				else:
					logging.error('Unexpected Error.')
					logging.shutdown()
					sys.exit(1)

			if (
				not isinstance(desc['Cover'], str)
				and not isinstance(desc['Taglist'], str)
				and not isinstance(desc['Title'], str)
			):
				for key in ('Cover', 'Taglist', 'Title'):
					if not isinstance(desc.get(key), str):
						raise TypeError(
							f"Expected '{key}' to be a string, got {type(desc.get(key)).__name__}"
						)

		except (AttributeError, HTTPError, KeyError, TypeError) as e:
			logging.error(f'{type(e).__name__}: {e}')
			logging.shutdown()
			sys.exit(1)

	if 50.00 <= percentage <= 100.00 and choice in ['no', 'n']:
		logging.warning('Skipping torrent.')


def main() -> None:
	parser = parse_torpost()
	args = parser.parse_args(sys.argv[1:])

	for f in args.filepath:
		json_path = Path(f)

		if json_path.suffix != '.json':
			logging.error(f'Wrong extension: json only.{os.linesep}{json_path}')
			logging.shutdown()
			sys.exit(1)

		name = json_path.stem
		desc_path = CONFIG.desc_path / f'{name}.txt'
		desc = build_desc(json_path)
		style = desc['Style']

		if isinstance(style, str):
			bbcode, text = make_bbcode(desc_path, desc, style)
			rprint(preview_desc(desc, text))

			if not args.no_prompts:
				input(f'Press Enter to exit preview{os.linesep}')

			no_prompts = True if args.no_prompts else False

			for t in args.tracker:
				if args.collage and [c for c in args.collage if c.split('-')[0] == t]:
					collages = [c for c in args.collage if c.split('-')[0] == t]
					logging.info(
						f'Found matching collage_id(s) {collages} for tracker {t}.'
					)

				post_torrent(
					bbcode,
					desc,
					name,
					t,
					collages if collages else None,
					no_prompts,
				)

				if not args.no_prompts:
					input(f'{os.linesep}Press Enter')

		if not isinstance(style, str):
			logging.error(f'Expected str for Style, got {type(style).__name__}')
			logging.shutdown()
			sys.exit(1)


if __name__ == '__main__':
	main()
