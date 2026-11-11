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

    public enum Needs
    {
        Any,
        MainMenu,
        Level,
        City,
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
            CoreOps.Register();
            CityOps.Register();
            PanelOps.Register();
            NetworkOps.Register();
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

        public static string[] ErrorSnapshot(out int count)
        {
            lock (Errors)
            {
                count = errorCount;
                return Errors.ToArray();
            }
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

        public static float FrameMs = 0;

        void Update()
        {
            // Smoothed render frame time, for checking that observers don't slow the game.
            float ms = Time.unscaledDeltaTime * 1000f;
            FrameMs = FrameMs <= 0 ? ms : FrameMs * 0.95f + ms * 0.05f;
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

        public static string Scene()
        {
            return SceneManager.GetActiveScene().name;
        }

        static ItemClass.Availability Mode()
        {
            var tm = Singleton<ToolManager>.exists ? Singleton<ToolManager>.instance : null;
            return tm == null || tm.m_properties == null ? ItemClass.Availability.None : tm.m_properties.m_mode;
        }

        // A city (or any editor level) has finished loading.
        public static bool LevelLoaded()
        {
            return Singleton<LoadingManager>.instance.m_loadingComplete
                && !Singleton<LoadingManager>.instance.m_currentlyLoading
                && Mode() != ItemClass.Availability.None;
        }

        public static bool InGame()
        {
            return LevelLoaded() && (Mode() & ItemClass.Availability.Game) != ItemClass.Availability.None;
        }

        public static void RequestQuit()
        {
            instance.quitRequested = true;
        }

        // -- op registry ------------------------------------------------------
        // Each module (CoreOps, CityOps, and later e.g. an asset-editor module)
        // registers its ops from Awake. "ops" lists them, so a CLI or MCP server
        // can discover what this build of the mod can do.

        public delegate Dictionary<string, object> OpFn(Dictionary<string, object> q);

        sealed class OpInfo
        {
            public Needs Needs;
            public string Help;
            public OpFn Fn;
        }

        static readonly Dictionary<string, OpInfo> Registry = new Dictionary<string, OpInfo>();

        public static void Register(string name, Needs needs, string help, OpFn fn)
        {
            Registry[name] = new OpInfo { Needs = needs, Help = help, Fn = fn };
        }

        static Dictionary<string, object> ListOps()
        {
            var ops = new List<object>();
            foreach (var kv in Registry)
                ops.Add(Obj("op", kv.Key, "needs", kv.Value.Needs.ToString(), "help", kv.Value.Help));
            return Obj("protocol", Protocol, "ops", ops);
        }

        Dictionary<string, object> Execute(Dictionary<string, object> q)
        {
            string op = Json.Str(q, "op", "");
            if (op == "ops")
                return ListOps();
            OpInfo info;
            if (!Registry.TryGetValue(op, out info))
                throw new Exception("unknown op '" + op + "'; 'ops' lists them");
            bool ok;
            switch (info.Needs)
            {
                case Needs.MainMenu:
                    ok = !Singleton<LoadingManager>.instance.m_currentlyLoading && !LevelLoaded();
                    break;
                case Needs.Level:
                    ok = LevelLoaded();
                    break;
                case Needs.City:
                    ok = InGame();
                    break;
                default:
                    ok = true;
                    break;
            }
            if (!ok)
                throw new Exception("op '" + op + "' needs " + info.Needs + "; scene is " + Scene());
            return info.Fn(q);
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
