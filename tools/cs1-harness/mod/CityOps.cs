using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using ColossalFramework;
using ColossalFramework.Packaging;
using ColossalFramework.Plugins;
using ColossalFramework.UI;
using ICities;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Cs1Harness
{
    // Map checks: New Game from a map, city stats, water probes and grids.
    public static class CityOps
    {
        public static void Register()
        {
            Host.Register("maps", Needs.Any, "list map assets the game knows", q => Maps());
            Host.Register("new_game", Needs.MainMenu, "New Game from a map file in Maps/: {path, city}", NewGame);
            Host.Register("stats", Needs.City, "frame, game time, population, buildings, money, sea level", q => Stats());
            Host.Register("water", Needs.City, "water at points [[x,z],...] plus sources and whole-map totals", Water);
            Host.Register("dump", Needs.City, "write raw water (and terrain) grids: {dir, prefix, terrain}", Dump);
        }

        static Dictionary<string, object> Maps()
        {
            var maps = new List<object>();
            foreach (var a in PackageManager.FilterAssets(UserAssetType.MapMetaData))
            {
                if (a == null || !a.isEnabled)
                    continue;
                MapMetaData m = null;
                try
                {
                    m = a.Instantiate<MapMetaData>();
                }
                catch { }
                maps.Add(Host.Obj(
                    "name", a.name,
                    "package", a.package.packageName,
                    "path", a.package.packagePath,
                    "map_name", m == null ? null : m.mapName,
                    "published", m != null && m.isPublished
                ));
            }
            return Host.Obj("maps", maps);
        }

        // Mirrors NewGamePanel.StartNewGameRoutine for the selected map, with the
        // city named after the map and inverted traffic off.
        static Dictionary<string, object> NewGame(Dictionary<string, object> q)
        {
            var lm = Singleton<LoadingManager>.instance;
            if (lm.m_currentlyLoading || Host.InGame())
                throw new Exception("new_game needs the idle main menu");
            string path = Path.GetFullPath(Json.Str(q, "path", ""));
            Package.Asset asset = null;
            foreach (var a in PackageManager.FilterAssets(UserAssetType.MapMetaData))
                if (a != null && a.package.packagePath != null && Path.GetFullPath(a.package.packagePath) == path)
                {
                    if (asset != null)
                        throw new Exception("more than one map asset in " + path);
                    asset = a;
                }
            if (asset == null)
                throw new Exception("no map asset at " + path + "; is the file in Maps/ and did the game start after it was copied?");
            var meta = asset.Instantiate<MapMetaData>();
            var sim = new SimulationMetaData
            {
                m_CityName = Json.Str(q, "city", meta.mapName),
                m_gameInstanceIdentifier = Guid.NewGuid().ToString(),
                m_invertTraffic = SimulationMetaData.MetaBool.False,
                m_disableAchievements = SimulationMetaData.MetaBool.False,
                m_startingDateTime = DateTime.Now,
                m_currentDateTime = DateTime.Now,
                m_newGameAppVersion = 222554386u,
                m_updateMode = SimulationManager.UpdateMode.NewGameFromMap,
                m_MapName = meta.mapName,
            };
            if (meta.mapThemeRef != null)
            {
                var theme = PackageManager.FindAssetByName(meta.mapThemeRef, UserAssetType.MapThemeMetaData);
                if (theme != null)
                {
                    sim.m_MapThemeMetaData = theme.Instantiate<MapThemeMetaData>();
                    sim.m_MapThemeMetaData.SetSelfRef(theme);
                }
            }
            if (lm.LoadLevel(meta.assetRef, "Game", "InGame", sim) == null)
                throw new Exception("LoadingManager refused the map");
            return Host.Obj("loading", path, "map_name", meta.mapName, "published", meta.isPublished);
        }

        internal static Dictionary<string, object> Stats()
        {
            var sm = Singleton<SimulationManager>.instance;
            var district = Singleton<DistrictManager>.instance.m_districts.m_buffer[0];
            var water = Singleton<TerrainManager>.instance.WaterSimulation;
            return Host.Obj(
                "frame", sm.m_currentFrameIndex,
                "game_time", sm.m_currentGameTime.ToString("yyyy-MM-ddTHH:mm:ss"),
                "paused", sm.SimulationPaused,
                "speed", sm.SelectedSimulationSpeed,
                "final_speed", sm.FinalSimulationSpeed,
                "population", district.m_populationData.m_finalCount,
                "buildings", Singleton<BuildingManager>.instance.m_buildingCount,
                "segments", Singleton<NetManager>.instance.m_segmentCount,
                "citizens", Singleton<CitizenManager>.instance.m_citizenCount,
                "money", Singleton<EconomyManager>.instance.LastCashAmount,
                "sea_level", water.m_currentSeaLevel
            );
        }

        static Dictionary<string, object> Water(Dictionary<string, object> q)
        {
            var tm = Singleton<TerrainManager>.instance;
            var water = tm.WaterSimulation;
            var samples = new List<object>();
            if (q.ContainsKey("points"))
                foreach (var v in (List<object>)q["points"])
                {
                    var p = Point(v);
                    float ground, surface;
                    Vector3 velocity, normal;
                    bool wet = tm.SampleWaterData(new Vector2(p.x, p.z), out ground, out surface, out velocity, out normal);
                    samples.Add(Host.Obj(
                        "x", p.x, "z", p.z,
                        "terrain", tm.SampleRawHeightSmooth(p),
                        "ground", ground,
                        "surface", surface,
                        "depth", wet ? surface - ground : 0f,
                        "wet", wet,
                        "velocity", new object[] { velocity.x, velocity.y, velocity.z }
                    ));
                }
            var sources = new List<object>();
            for (int i = 0; i < water.m_waterSources.m_size; i++)
            {
                var s = water.m_waterSources.m_buffer[i];
                if (s.m_type == 0)
                    continue;
                sources.Add(Host.Obj(
                    "id", i + 1,
                    "type", s.m_type,
                    "x", s.m_inputPosition.x,
                    "z", s.m_inputPosition.z,
                    "target", s.m_target / 64f,
                    "input_rate", s.m_inputRate,
                    "output_rate", s.m_outputRate,
                    "flow", s.m_flow
                ));
            }
            var cells = water.BeginRead();
            long wetCells = 0, depthSum = 0;
            int maxDepth = 0;
            try
            {
                foreach (Dictionary<string, object> point in samples)
                {
                    float px = Convert.ToSingle(point["x"]), pz = Convert.ToSingle(point["z"]);
                    int cx = Mathf.RoundToInt((px + 8640f) / 16f), cz = Mathf.RoundToInt((pz + 8640f) / 16f);
                    int localMax = 0;
                    float nearest = float.PositiveInfinity;
                    for (int z = Mathf.Max(0, cz - 4); z <= Mathf.Min(1080, cz + 4); z++)
                        for (int x = Mathf.Max(0, cx - 4); x <= Mathf.Min(1080, cx + 4); x++)
                        {
                            float dx = x * 16 - 8640 - px, dz = z * 16 - 8640 - pz;
                            float squared = dx * dx + dz * dz;
                            if (squared > 64 * 64)
                                continue;
                            int h = cells[z * 1081 + x].m_height;
                            localMax = Mathf.Max(localMax, h);
                            if (h >= 7)
                                nearest = Mathf.Min(nearest, squared);
                        }
                    point["max_depth_within_64m"] = localMax / 64f;
                    point["wet_within_64m"] = localMax >= 7;
                    point["nearest_water_m"] = float.IsPositiveInfinity(nearest) ? null : (object)Mathf.Sqrt(nearest);
                }
                for (int i = 0; i < cells.Length; i++)
                {
                    int h = cells[i].m_height;
                    if (h > 0)
                    {
                        wetCells++;
                        depthSum += h;
                        if (h > maxDepth)
                            maxDepth = h;
                    }
                }
            }
            finally
            {
                water.EndRead();
            }
            const double cellArea = 16.0 * 16.0;
            return Host.Obj(
                "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex,
                "samples", samples,
                "sources", sources,
                "wet_cells", wetCells,
                "volume_m3", depthSum / 64.0 * cellArea,
                "max_depth_m", maxDepth / 64.0,
                "sea_level", water.m_currentSeaLevel
            );
        }

        // Raw grids for offline comparison: little-endian ushort, 1081 x 1081,
        // the game's own order: index = iz * 1081 + ix, world x = ix * 16 - 8640,
        // world z = iz * 16 - 8640. Water is depth in 1/64 m; terrain is raw
        // height in 1/64 m.
        static Dictionary<string, object> Dump(Dictionary<string, object> q)
        {
            string dir = Json.Str(q, "dir", "");
            if (string.IsNullOrEmpty(dir) || !Path.IsPathRooted(dir))
                throw new Exception("dump needs an absolute dir");
            Directory.CreateDirectory(dir);
            string prefix = Json.Str(q, "prefix", "grid");
            var water = Singleton<TerrainManager>.instance.WaterSimulation;
            var cells = water.BeginRead();
            byte[] w = new byte[cells.Length * 2];
            try
            {
                for (int i = 0; i < cells.Length; i++)
                {
                    w[2 * i] = (byte)(cells[i].m_height & 0xff);
                    w[2 * i + 1] = (byte)(cells[i].m_height >> 8);
                }
            }
            finally
            {
                water.EndRead();
            }
            string waterPath = Path.Combine(dir, prefix + "-water.u16");
            File.WriteAllBytes(waterPath, w);
            var result = Host.Obj("water", waterPath, "cells", cells.Length, "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex);
            if (Json.Bool(q, "terrain", false))
            {
                ushort[] raw = Singleton<TerrainManager>.instance.RawHeights;
                byte[] t = new byte[raw.Length * 2];
                Buffer.BlockCopy(raw, 0, t, 0, t.Length);
                string terrainPath = Path.Combine(dir, prefix + "-terrain.u16");
                File.WriteAllBytes(terrainPath, t);
                result["terrain"] = terrainPath;
            }
            return result;
        }

        static Vector3 Point(object v)
        {
            var a = v as List<object>;
            if (a == null || a.Count < 2)
                throw new Exception("points are [x, z] world metres");
            return new Vector3(Convert.ToSingle(a[0]), 0, Convert.ToSingle(a[a.Count == 2 ? 1 : 2]));
        }
    }
}
