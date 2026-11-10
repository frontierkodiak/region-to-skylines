// CS1 Harness: a loopback control socket for automated map checks.
//
// The game constructs every local mod's IUserMod instance at startup, enabled
// or not (PluginManager.AddPlugins), so the socket starts from the constructor
// and the mod never has to be ticked in Content Manager. A disabled mod leaves
// the game's own enabled-mod count at zero, which keeps the session as close
// to vanilla as a controllable session can be.
//
// Protocol: one JSON object per line in, one JSON object per line out, on
// 127.0.0.1 (port 8779, or CS1_HARNESS_PORT). Requests run on Unity's main
// thread between frames. Nothing here saves a city or a map.

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
    public sealed class Mod : IUserMod
    {
        public Mod()
        {
            Host.Start();
        }

        public string Name
        {
            get { return "CS1 Harness"; }
        }

        public string Description
        {
            get { return "Loopback control socket for automated map checks (PL-856)."; }
        }
    }

    public sealed class Host : MonoBehaviour
    {
        public const int Protocol = 1;
        static Host instance;
        static readonly Queue<Work> Pending = new Queue<Work>();
        static readonly List<string> Errors = new List<string>();
        static int errorCount;
        TcpListener listener;
        Thread acceptThread;
        volatile bool stopping;
        bool autosaveStopped;
        bool quitRequested;

        sealed class Work
        {
            public Dictionary<string, object> Request;
            public string Response;
            public readonly ManualResetEvent Done = new ManualResetEvent(false);
        }

        public static void Start()
        {
            if (instance != null)
                return;
            var go = new GameObject("Cs1Harness");
            DontDestroyOnLoad(go);
            instance = go.AddComponent<Host>();
        }

        void Awake()
        {
            int port = 8779;
            string env = Environment.GetEnvironmentVariable("CS1_HARNESS_PORT");
            if (!string.IsNullOrEmpty(env))
                port = int.Parse(env);
            Application.logMessageReceived += OnLog;
            listener = new TcpListener(IPAddress.Loopback, port);
            listener.Start();
            acceptThread = new Thread(Accept) { IsBackground = true, Name = "Cs1Harness" };
            acceptThread.Start();
            Debug.Log("[Cs1Harness] listening 127.0.0.1:" + port + " protocol " + Protocol);
        }

        void OnDestroy()
        {
            stopping = true;
            try
            {
                listener.Stop();
            }
            catch { }
        }

        static void OnLog(string message, string stack, LogType type)
        {
            if (type != LogType.Exception && type != LogType.Error && type != LogType.Assert)
                return;
            lock (Errors)
            {
                errorCount++;
                if (Errors.Count < 200)
                    Errors.Add(type + ": " + message);
            }
        }

        void Accept()
        {
            while (!stopping)
            {
                TcpClient client;
                try
                {
                    client = listener.AcceptTcpClient();
                }
                catch
                {
                    if (stopping)
                        return;
                    Thread.Sleep(100);
                    continue;
                }
                var t = new Thread(() => Serve(client)) { IsBackground = true };
                t.Start();
            }
        }

        void Serve(TcpClient client)
        {
            using (client)
            using (var stream = client.GetStream())
            using (var reader = new StreamReader(stream, new UTF8Encoding(false)))
            using (var writer = new StreamWriter(stream, new UTF8Encoding(false)))
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    string response;
                    try
                    {
                        var request = Json.Parse(line) as Dictionary<string, object>;
                        if (request == null)
                            throw new Exception("request must be a JSON object");
                        var work = new Work { Request = request };
                        lock (Pending)
                            Pending.Enqueue(work);
                        if (!work.Done.WaitOne(120000))
                            throw new Exception("main thread did not run the request within 120 s");
                        response = work.Response;
                    }
                    catch (Exception e)
                    {
                        response = Json.Write(Obj("ok", false, "error", e.Message));
                    }
                    writer.Write(response);
                    writer.Write('\n');
                    writer.Flush();
                }
            }
        }

        void Update()
        {
            if (!autosaveStopped && InGame() && Singleton<LoadingManager>.instance.m_loadingComplete)
            {
                // A harness city is never saved. Stop this process's autosave timer
                // without touching the player's persistent autosave preference.
                Singleton<LoadingManager>.instance.autoSaveTimer.Stop();
                autosaveStopped = true;
            }
            if (!InGame())
                autosaveStopped = false;
            for (int i = 0; i < 8; i++)
            {
                Work w = null;
                lock (Pending)
                    if (Pending.Count > 0)
                        w = Pending.Dequeue();
                if (w == null)
                    break;
                try
                {
                    var result = Execute(w.Request);
                    result["ok"] = true;
                    w.Response = Json.Write(result);
                }
                catch (Exception e)
                {
                    w.Response = Json.Write(Obj("ok", false, "error", e.Message, "exception", e.GetType().Name));
                }
                w.Done.Set();
            }
            if (quitRequested)
            {
                quitRequested = false;
                Application.Quit();
            }
        }

        static string Scene()
        {
            return SceneManager.GetActiveScene().name;
        }

        static bool InGame()
        {
            var tm = Singleton<ToolManager>.exists ? Singleton<ToolManager>.instance : null;
            return tm != null
                && tm.m_properties != null
                && (tm.m_properties.m_mode & ItemClass.Availability.Game) != ItemClass.Availability.None
                && Singleton<LoadingManager>.instance.m_loadingComplete;
        }

        Dictionary<string, object> Execute(Dictionary<string, object> q)
        {
            string op = Json.Str(q, "op", "");
            switch (op)
            {
                case "status":
                    return Status();
                case "maps":
                    return Maps();
                case "new_game":
                    return NewGame(q);
                case "quit":
                    quitRequested = true;
                    return Obj("quitting", true);
            }
            if (!InGame())
                throw new Exception("op '" + op + "' needs a loaded city; scene is " + Scene());
            switch (op)
            {
                case "run":
                    return Run(q);
                case "stats":
                    return Stats();
                case "water":
                    return Water(q);
                case "dump":
                    return Dump(q);
                case "camera":
                    return CameraOp(q);
                case "ui":
                    UIView.Show(Json.Bool(q, "visible", true));
                    return Obj("ui_visible", Json.Bool(q, "visible", true));
                case "screenshot":
                    return Screenshot(q);
            }
            throw new Exception("unknown op '" + op + "'");
        }

        static Dictionary<string, object> Status()
        {
            var lm = Singleton<LoadingManager>.instance;
            var plugins = new List<object>();
            foreach (var p in Singleton<PluginManager>.instance.GetPluginsInfo())
                plugins.Add(Obj("name", p.name, "enabled", p.isEnabled, "builtin", p.isBuiltin, "path", p.modPath));
            string[] errors;
            int count;
            lock (Errors)
            {
                errors = Errors.ToArray();
                count = errorCount;
            }
            var result = Obj(
                "protocol", Protocol,
                "scene", Scene(),
                "in_game", InGame(),
                "loading", lm.m_currentlyLoading,
                "loading_complete", lm.m_loadingComplete,
                "unity", Application.unityVersion,
                "gpu", SystemInfo.graphicsDeviceName,
                "gpu_memory_mb", SystemInfo.graphicsMemorySize,
                "screen", new object[] { Screen.width, Screen.height },
                "fixed_delta_time", Time.fixedDeltaTime,
                "enabled_mod_count", Singleton<PluginManager>.instance.enabledModCount,
                "plugins", plugins,
                "error_count", count,
                "errors", errors
            );
            if (InGame())
                foreach (var kv in Stats())
                    result[kv.Key] = kv.Value;
            return result;
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
                maps.Add(Obj(
                    "name", a.name,
                    "package", a.package.packageName,
                    "path", a.package.packagePath,
                    "map_name", m == null ? null : m.mapName,
                    "published", m != null && m.isPublished
                ));
            }
            return Obj("maps", maps);
        }

        // Mirrors NewGamePanel.StartNewGameRoutine for the selected map, with the
        // city named after the map and inverted traffic off.
        static Dictionary<string, object> NewGame(Dictionary<string, object> q)
        {
            var lm = Singleton<LoadingManager>.instance;
            if (lm.m_currentlyLoading || InGame())
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
            return Obj("loading", path, "map_name", meta.mapName, "published", meta.isPublished);
        }

        static Dictionary<string, object> Run(Dictionary<string, object> q)
        {
            var sm = Singleton<SimulationManager>.instance;
            if (q.ContainsKey("speed"))
            {
                int speed = (int)Json.Num(q, "speed", 1);
                if (speed < 1 || speed > 3)
                    throw new Exception("speed is 1, 2 or 3 (the game's buttons)");
                sm.SelectedSimulationSpeed = speed;
            }
            if (q.ContainsKey("paused"))
                sm.SimulationPaused = Json.Bool(q, "paused", true);
            return Obj("paused", sm.SimulationPaused, "speed", sm.SelectedSimulationSpeed, "final_speed", sm.FinalSimulationSpeed);
        }

        static Dictionary<string, object> Stats()
        {
            var sm = Singleton<SimulationManager>.instance;
            var district = Singleton<DistrictManager>.instance.m_districts.m_buffer[0];
            var water = Singleton<TerrainManager>.instance.WaterSimulation;
            return Obj(
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

        static Vector3 Point(object v)
        {
            var a = v as List<object>;
            if (a == null || a.Count < 2)
                throw new Exception("points are [x, z] world metres");
            return new Vector3(Convert.ToSingle(a[0]), 0, Convert.ToSingle(a[a.Count == 2 ? 1 : 2]));
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
                    samples.Add(Obj(
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
                sources.Add(Obj(
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
            return Obj(
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
            var result = Obj("water", waterPath, "cells", cells.Length, "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex);
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

        static Dictionary<string, object> CameraOp(Dictionary<string, object> q)
        {
            var c = ToolsModifierControl.cameraController;
            if (Json.Bool(q, "release", false))
            {
                c.SetOverrideModeOff();
                return Obj("camera", "released");
            }
            // [x, z] targets the terrain surface there; [x, y, z] is explicit.
            var p = (List<object>)q["position"];
            Vector3 pos;
            if (p.Count == 2)
            {
                pos = new Vector3(Convert.ToSingle(p[0]), 0, Convert.ToSingle(p[1]));
                pos.y = Singleton<TerrainManager>.instance.SampleRawHeightSmooth(pos);
            }
            else
                pos = new Vector3(Convert.ToSingle(p[0]), Convert.ToSingle(p[1]), Convert.ToSingle(p[2]));
            var angle = new Vector2((float)Json.Num(q, "yaw", 0), (float)Json.Num(q, "pitch", 60));
            float size = (float)Json.Num(q, "size", 2000);
            c.m_targetPosition = pos;
            c.m_targetAngle = angle;
            c.m_targetSize = size;
            c.SetOverrideModeOn(pos, angle, size);
            return Obj("camera", new object[] { pos.x, pos.y, pos.z }, "yaw", angle.x, "pitch", angle.y, "size", size);
        }

        static Dictionary<string, object> Screenshot(Dictionary<string, object> q)
        {
            string path = Json.Str(q, "path", "");
            if (string.IsNullOrEmpty(path) || !Path.IsPathRooted(path))
                throw new Exception("screenshot needs an absolute path");
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            if (File.Exists(path))
                File.Delete(path);
            // Written at the end of the current frame; the caller waits for the file.
            Application.CaptureScreenshot(path, (int)Json.Num(q, "supersize", 1));
            return Obj("path", path, "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex);
        }

        public static Dictionary<string, object> Obj(params object[] kv)
        {
            var d = new Dictionary<string, object>();
            for (int i = 0; i + 1 < kv.Length; i += 2)
                d[(string)kv[i]] = kv[i + 1];
            return d;
        }
    }
}
