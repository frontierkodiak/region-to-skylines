using System;
using System.Collections.Generic;
using ColossalFramework;
using UnityEngine;

namespace Cs1Harness
{
    // Read-only observations in native world axes; never changes camera or terrain.
    public static class WorldOps
    {
        public static void Register()
        {
            Host.Register("world_observe", Needs.Level,
                "native terrain heights at {points:[{name,x,z}]} and actual/current/target camera, including Area Zoom", Observe);
        }

        static object[] Vec(Vector3 v) { return new object[] { v.x, v.y, v.z }; }
        static object[] Angle(Vector2 v) { return new object[] { v.x, v.y }; }

        static Dictionary<string, object> Observe(Dictionary<string, object> q)
        {
            var terrain = Singleton<TerrainManager>.instance;
            var samples = new List<object>();
            if (q.ContainsKey("points"))
                foreach (var item in (List<object>)q["points"])
                {
                    var point = (Dictionary<string, object>)item;
                    float x = Convert.ToSingle(point["x"]), z = Convert.ToSingle(point["z"]);
                    if (float.IsNaN(x) || float.IsInfinity(x) || float.IsNaN(z) || float.IsInfinity(z)
                        || Mathf.Abs(x) > 8640f || Mathf.Abs(z) > 8640f)
                        throw new Exception("world_observe points must be finite native world coordinates inside +/-8640m");
                    samples.Add(Host.Obj("name", Json.Str(point, "name", ""), "x", point["x"], "z", point["z"],
                        "sample_position", new object[] { x, 0f, z },
                        "height_m", terrain.SampleRawHeightSmooth(new Vector3(x, 0, z))));
                }
            var controller = ToolsModifierControl.cameraController;
            if (controller == null) throw new Exception("no native camera controller");
            // Public native snapshot reads the private interpolated current fields.
            var current = new CameraController.SavedCameraView(controller);
            var camera = controller.GetComponent<Camera>();
            if (camera == null) throw new Exception("no native render camera");
            Vector3 forward = camera.transform.forward;
            float horizontal = new Vector2(forward.x, forward.z).magnitude;
            var observation = Host.Obj(
                "current_position", Vec(current.m_position), "current_size", current.m_size,
                "current_height", current.m_height, "current_angle_degrees", Angle(current.m_angle),
                "target_position", Vec(controller.m_targetPosition), "target_size", controller.m_targetSize,
                "target_angle_degrees", Angle(controller.m_targetAngle),
                "render_position", Vec(camera.transform.position), "render_forward", Vec(forward),
                "render_up", Vec(camera.transform.up), "render_euler_degrees", Vec(camera.transform.eulerAngles),
                "render_heading_degrees", horizontal < 0.00001f ? null : (object)Mathf.Repeat(Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg, 360f),
                "areas_visible", Singleton<GameAreaManager>.instance.AreasVisible);
            return Host.Obj("source", "TerrainManager.SampleRawHeightSmooth/world camera", "points", samples,
                "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex, "camera", observation);
        }
    }
}
