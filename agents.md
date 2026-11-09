# Region to Cities: Skylines: instructions for AI agents

Your person wants a real place as a Cities: Skylines (CS1, the first game) map. This tool
turns a square of real terrain into the game's 1081 x 1081 px, 16-bit heightmap, with rivers
and lakes carved from OpenStreetMap, and can copy it into the game's folder. Do the setup for
them; leave only the in-game steps to them.

## 1. Run one command

You need Node.js 20.3 or newer and git. No account, key or install is needed.

```sh
npx -y github:frontierkodiak/region-to-skylines "<where>" --install
```

`<where>` is whichever your person gave you:

- a link from <https://region-to-skylines.vercel.app> (it keeps the square's centre,
  rotation, scale and options, so the map matches what they saw), in quotes;
- `"lat,lon"` in decimal degrees, latitude first, e.g. `"35.58,-82.555"`;
- a place name, e.g. `"Innsbruck"` (looked up once on OpenStreetMap's Nominatim).

It writes `<name>.png` and `<name>.json` to the current directory and, with `--install`,
copies the PNG into the game's heightmap folder:

| OS | Folder |
|---|---|
| macOS | `~/Library/Application Support/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps` |
| Windows | `%LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\MapEditor\Heightmaps` |
| Linux | `~/.local/share/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps` |

Useful options: `--name <name>` (file name), `--out <dir>`, `--rotate <deg>`, `--scale
0.5|0.75|1|1.5|2` (1 = true size, 17.28 km), `--height auto|slopes|<factor>`,
`--game-dir <dir>` (the game's data folder when it isn't the usual one), `--force`
(replace a file of the same name), `--json` (machine-readable summary on stdout).
`--help` lists everything.

Exit codes: 0 done; 1 bad arguments; 2 a download failed (retry in a minute); 3 the game's
data folder doesn't exist (the game hasn't been started on this computer, or it lives
elsewhere: ask, then pass `--game-dir`); 4 a file of that name exists (ask before `--force`,
or pick another `--name`).

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
3. **Water:** place a water source at each spot it listed (river entries and starts, and
   lakes), using the editor's Water tool; nothing where a river leaves.
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
