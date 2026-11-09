# Region to Cities: Skylines: instructions for AI agents

Your person wants a real place as a Cities: Skylines (CS1, the first game) map. This tool
turns a square of real terrain into the game's 1081 x 1081 px, 16-bit heightmap, with rivers
and lakes carved from OpenStreetMap, and can copy it into the game's folder. Do the setup for
them; leave only the in-game steps to them.

## 1. Run one command

You need Node.js 20.3 or newer (it comes with npx). No git, account, key or install is needed.

```sh
npx -y __CLI_TGZ__ "<where>" --install
```

`<where>` is whichever your person gave you:

- a link from <https://region-to-skylines.vercel.app> (it keeps the square's centre,
  rotation, scale and options, so the map matches what they saw), in quotes;
- `"lat,lon"` in decimal degrees, latitude first, e.g. `"35.58,-82.555"`;
- a place name, e.g. `"Innsbruck"` (looked up once on OpenStreetMap's Nominatim).

The command is pinned to the commit the page runs, so it makes the same pixels the page
shows. With `--install` it puts `<name>.png` into the game's heightmap folder, and keeps
`<name>.json` and `<name>-water.png` (the map with the water-source spots pinned) in this
OS's cache folder (`~/Library/Caches/region-to-skylines` on macOS,
`%LOCALAPPDATA%\region-to-skylines` on Windows, `~/.cache/region-to-skylines` on Linux).
Without `--install`, or with `--out <dir>`, all three go to that folder (default: the
current directory, so pass `--out` rather than writing into your person's home or a repo).

| OS | Heightmap folder |
|---|---|
| macOS | `~/Library/Application Support/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps` |
| Windows | `%LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\MapEditor\Heightmaps` |
| Linux | `~/.local/share/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps` |

Useful options: `--name <name>` (file name), `--out <dir>`, `--rotate <deg>`, `--scale
0.5|0.75|1|1.5|2` (1 = true size, 17.28 km), `--height auto|slopes|<factor>`,
`--game-dir <dir>` (the game's data folder when it isn't the usual one), `--force`
(replace a file of the same name), `--json` (machine-readable summary on stdout).
`--help` lists everything.

Exit codes: 0 done; 1 bad arguments (including a hand-edited link with values the page
can't make); 2 a download failed (retry in a minute); 3 the game's data folder doesn't
exist (the game hasn't been started on this computer, or it lives elsewhere: ask, then pass
`--game-dir`); 4 a file of that name exists (ask before `--force`, or pick another `--name`).

**WSL:** the game runs on Windows, so pass
`--game-dir "/mnt/c/Users/<user>/AppData/Local/Colossal Order/Cities_Skylines"`.

**No Node?** Send your person to the link instead: the page builds the same file in the
browser ("Download heightmap"), and you can tell them which folder above to save it in.

## 2. Tell your person what to do next

The command prints the steps with this map's numbers filled in. Pass them on plainly:

1. Start Cities: Skylines. Main menu > Tools > Map Editor, start a new map, press
   **Import heightmap** and pick the map's name.
2. **Sea level:** the value the command printed (coastal maps), or below the lowest
   riverbed it printed (inland maps).
3. **Water:** with the editor's Water tool, place a source at each numbered pin. Show them
   the water map the command wrote (`<name>-water.png`; open it for them if you can), or
   send them to the square's link, where "Water sources for the Map Editor" lists the same
   numbered spots beside a 3D preview. The printed list says each spot in words ("top
   edge, 30% from the left", in the heightmap's own frame); the editor shows no
   coordinates, so don't pass on the metre values in the JSON. Grey pins mark where a
   river leaves: nothing goes there.
4. The start tile needs water and a highway in and out. Save the map; New Game lists it.
5. If they use the 81 Tiles 2 mod, it must be disabled while the Map Editor is open.

A ready-to-play map file that skips the Map Editor is in the works; until then the Map
Editor steps above are needed once per map.

## Notes

- Same code as the web page: a square gives the same heightmap pixels here as in the browser.
- Data: elevation from AWS Terrain Tiles (Mapzen and its sources); rivers and lakes
  © OpenStreetMap contributors (ODbL), via OpenFreeMap tiles; place search by Nominatim.
  If your person shares the map, credit "© OpenStreetMap contributors".
- Source and issues: <https://github.com/frontierkodiak/region-to-skylines>.
