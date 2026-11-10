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
    // Controls any level needs: status, speed, camera, UI, screenshots, quit.
    public static class CoreOps
    {
        public static void Register()
        {
            Host.Register("status", Needs.Any, "process, scene, GPU, plugins, errors; city stats when a city is loaded", q => Status());
            Host.Register("quit", Needs.Any, "quit the game after this frame", q => { Host.RequestQuit(); return Host.Obj("quitting", true); });
            Host.Register("run", Needs.Level, "pause/unpause and set speed 1-3: {paused, speed}", Run);
            Host.Register("camera", Needs.Level, "aim the camera: {position:[x,z]|[x,y,z], size, yaw, pitch} or {release:true}", CameraOp);
            Host.Register("ui", Needs.Level, "show or hide the game UI: {visible}", q => { UIView.Show(Json.Bool(q, "visible", true)); return Host.Obj("ui_visible", Json.Bool(q, "visible", true)); });
            Host.Register("screenshot", Needs.Level, "write a PNG at the end of this frame: {path (absolute), supersize}", Screenshot);
        }

        static Dictionary<string, object> Status()
        {
            var lm = Singleton<LoadingManager>.instance;
            var plugins = new List<object>();
            foreach (var p in Singleton<PluginManager>.instance.GetPluginsInfo())
                plugins.Add(Host.Obj("name", p.name, "enabled", p.isEnabled, "builtin", p.isBuiltin, "path", p.modPath));
            int count;
            string[] errors = Host.ErrorSnapshot(out count);
            var result = Host.Obj(
                "protocol", Host.Protocol,
                "scene", Host.Scene(),
                "in_game", Host.InGame(),
                "in_asset_editor", Host.InAssetEditor(),
                "modal", Host.ModalStack(),
                "color_space", QualitySettings.activeColorSpace.ToString(),
                "safe_readback", Host.Obj("installed", Readback.Installed, "reads", Readback.Count, "from_cpu", Readback.FromCpu, "from_gpu", Readback.FromGpu),
                "mode", Host.Mode().ToString(),
                "loading", lm.m_currentlyLoading,
                "loading_complete", lm.m_loadingComplete,
                "unity", Application.unityVersion,
                "gpu", SystemInfo.graphicsDeviceName,
                "gpu_memory_mb", SystemInfo.graphicsMemorySize,
                "screen", new object[] { Screen.width, Screen.height },
                "fixed_delta_time", Time.fixedDeltaTime,
                "frame_ms", Host.FrameMs,
                "render_fps", Host.FrameMs > 0 ? 1000f / Host.FrameMs : 0f,
                "enabled_mod_count", Singleton<PluginManager>.instance.enabledModCount,
                "plugins", plugins,
                "error_count", count,
                "errors", errors
            );
            if (Host.InGame())
                foreach (var kv in CityOps.Stats())
                    result[kv.Key] = kv.Value;
            return result;
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
            return Host.Obj("paused", sm.SimulationPaused, "speed", sm.SelectedSimulationSpeed, "final_speed", sm.FinalSimulationSpeed);
        }

        static Dictionary<string, object> CameraOp(Dictionary<string, object> q)
        {
            var c = ToolsModifierControl.cameraController;
            if (Json.Bool(q, "release", false))
            {
                c.SetOverrideModeOff();
                return Host.Obj("camera", "released");
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
            return Host.Obj("camera", new object[] { pos.x, pos.y, pos.z }, "yaw", angle.x, "pitch", angle.y, "size", size);
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
            return Host.Obj("path", path, "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex);
        }
    }
}
