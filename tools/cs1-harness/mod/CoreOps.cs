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
            Host.Register("run", Needs.Level, "pause/speed and session-only day/night: {paused, speed, day_night}", Run);
            Host.Register("camera", Needs.Level, "aim the camera: {position:[x,z]|[x,y,z], size, yaw, pitch} or {release:true}", CameraOp);
            Host.Register("ui", Needs.Level, "show or hide the game UI: {visible}", Ui);
            Host.Register("guide_controls", Needs.City, "inspect visible native close buttons; click an exact tutorial-only button with {id}; refuses modals", GuideControls);
            Host.Register("camera_state", Needs.Level, "where the camera is and which way it faces: position, heading (0 = +z, 90 = +x), pitch, size, max size", q => CameraState());
            Host.Register("area_zoom", Needs.Level, "open/close the native Areas tool (not camera zoom): {enabled}", AreaZoom);
            Host.Register("screenshot", Needs.Level, "write a PNG at the end of this frame: {path (absolute), supersize}", Screenshot);
            Host.Register("render", Needs.Any, "throttle drawing (the simulation runs on): {fps (0 = unlimited), camera (false: the main camera stops drawing the world)}", Render);
        }

        static Camera s_mainCamera;

        static Dictionary<string, object> GuideControls(Dictionary<string, object> q)
        {
            if (UIView.ModalInputCount() != 0) throw new Exception("refusing guide controls while a modal is open");
            int requested = (int)Json.Num(q, "id", 0);
            bool applied = false;
            var controls = new List<object>();
            foreach (var button in UIView.GetAView().GetComponentsInChildren<UIButton>(true))
            {
                if (!button.gameObject.activeInHierarchy || !button.isVisible || !button.isEnabled || button.name.IndexOf("close", StringComparison.OrdinalIgnoreCase) < 0) continue;
                bool tutorial = false;
                var ancestors = new List<object>();
                for (var node = button.transform; node != null; node = node.parent)
                {
                    var types = new List<object>();
                    foreach (var component in node.GetComponents<Component>())
                    {
                        string type = component.GetType().Name;
                        types.Add(type);
                        if (type == "TutorialPanel" || type == "TutorialAdvisorPanel") tutorial = true;
                    }
                    ancestors.Add(Host.Obj("name", node.name, "types", types));
                }
                int id = button.GetInstanceID();
                controls.Add(Host.Obj("id", id, "name", button.name, "tutorial", tutorial, "ancestors", ancestors));
                if (id == requested)
                {
                    if (!tutorial) throw new Exception("requested close button is not an ordinary tutorial guide");
                    button.SimulateClick();
                    applied = true;
                }
            }
            if (requested != 0 && !applied) throw new Exception("requested tutorial close button is not visible");
            return Host.Obj("source", "native UI close buttons and transform ancestors", "controls", controls, "applied", applied);
        }

        static Dictionary<string, object> Render(Dictionary<string, object> q)
        {
            if (q.ContainsKey("fps"))
            {
                int fps = (int)Json.Num(q, "fps", 0);
                QualitySettings.vSyncCount = 0;
                Application.targetFrameRate = fps > 0 ? fps : -1;
            }
            // Camera.main skips disabled cameras, so keep the one we turned off.
            var controller = ToolsModifierControl.cameraController;
            if (s_mainCamera == null && controller != null)
                s_mainCamera = controller.GetComponent<Camera>();
            if (q.ContainsKey("camera"))
            {
                if (s_mainCamera == null)
                    throw new Exception("no main camera in this scene");
                s_mainCamera.enabled = Json.Bool(q, "camera", true);
            }
            return Host.Obj(
                "target_fps", Application.targetFrameRate,
                "vsync", QualitySettings.vSyncCount,
                "camera", s_mainCamera != null && s_mainCamera.enabled
            );
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
            if (q.ContainsKey("day_night"))
                sm.m_enableDayNight = Json.Bool(q, "day_night", true);
            return Host.Obj("paused", sm.SimulationPaused, "speed", sm.SelectedSimulationSpeed, "final_speed", sm.FinalSimulationSpeed,
                "day_night", sm.m_enableDayNight);
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

        static Dictionary<string, object> Ui(Dictionary<string, object> q)
        {
            bool visible = Json.Bool(q, "visible", true);
            // The game's own "hide UI" is free-camera mode: it hides the UI, notifications, borders,
            // names and markers, and gives the world camera the full screen. Without it the world
            // stops above a 10.5% menu-bar strip that keeps the toolbar's last pixels.
            var c = ToolsModifierControl.cameraController;
            if (c != null)
                c.m_freeCamera = !visible;
            UIView.Show(visible);
            return Host.Obj("ui_visible", visible, "free_camera", c != null && c.m_freeCamera);
        }

        static Dictionary<string, object> CameraState()
        {
            var c = ToolsModifierControl.cameraController;
            if (c == null)
                throw new Exception("no camera controller in this scene");
            // Yaw turns about +y, so 0 looks along +z and 90 along +x (Unity's left-handed axes).
            float yaw = c.m_currentAngle.x;
            float heading = ((yaw % 360f) + 360f) % 360f;
            var cam = c.GetComponent<Camera>();
            var fwd = cam != null ? cam.transform.forward : Vector3.zero;
            return Host.Obj(
                "position", new object[] { c.m_currentPosition.x, c.m_currentPosition.y, c.m_currentPosition.z },
                "yaw", yaw,
                "heading_deg", heading,
                "pitch", c.m_currentAngle.y,
                "size", c.m_currentSize,
                "max_size", c.m_maxDistance,
                "forward", new object[] { fwd.x, fwd.y, fwd.z }
            );
        }

        static Dictionary<string, object> AreaZoom(Dictionary<string, object> q)
        {
            if (!q.ContainsKey("enabled") || !(q["enabled"] is bool))
                throw new Exception("area_zoom needs a boolean enabled");
            // Same tool transitions as the normal toolbar. GameAreaTool owns
            // AreasVisible and the native camera mapping; do not emulate it.
            if (Json.Bool(q, "enabled", false))
                ToolsModifierControl.SetTool<GameAreaTool>();
            else
                ToolsModifierControl.SetTool<DefaultTool>();
            var tool = ToolsModifierControl.toolController.CurrentTool;
            return Host.Obj("source", "native ToolsModifierControl", "tool", tool == null ? null : tool.GetType().Name,
                "areas_visible", Singleton<GameAreaManager>.instance.AreasVisible);
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
