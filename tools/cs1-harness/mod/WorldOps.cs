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
                "native terrain/camera; {points:[{name,x,z}], tree_radius:0..1000, screen_points:[{name,x,y}]} (screen pixels, top-left)", Observe);
        }

        static object[] Vec(Vector3 v) { return new object[] { v.x, v.y, v.z }; }
        static object[] Angle(Vector2 v) { return new object[] { v.x, v.y }; }

        static object TreesNear(Vector3 center, float radius, TerrainManager terrain)
        {
            int count = 0, hidden = 0, grown = 0, belowGround = 0;
            var examples = new List<object>();
            var trees = Singleton<TreeManager>.instance.m_trees.m_buffer;
            for (int i = 1; i < trees.Length; i++)
            {
                var tree = trees[i];
                if ((tree.m_flags & 3) != 1) continue;
                var position = tree.Position;
                if (new Vector2(position.x - center.x, position.z - center.z).sqrMagnitude > radius * radius) continue;
                count++;
                if (tree.Hidden) hidden++;
                if (tree.GrowState != 0) grown++;
                float ground = terrain.SampleRawHeightSmooth(position);
                if (ground - position.y > 5f) belowGround++;
                if (examples.Count < 8)
                    examples.Add(Host.Obj("id", i, "position", Vec(position), "terrain_height_m", ground,
                        "detail_height_m", terrain.SampleDetailHeight(position), "flags", tree.m_flags,
                        "grow_state", tree.GrowState, "prefab", tree.Info == null ? null : tree.Info.name));
            }
            return Host.Obj("radius_m", radius, "created", count, "hidden", hidden, "grown", grown,
                "roots_over_5m_below_raw_terrain", belowGround, "examples", examples);
        }

        static object ScreenSample(Camera camera, TerrainManager terrain, Dictionary<string, object> point)
        {
            float x = Convert.ToSingle(point["x"]), y = Convert.ToSingle(point["y"]);
            if (float.IsNaN(x) || float.IsInfinity(x) || float.IsNaN(y) || float.IsInfinity(y)
                || x < 0 || y < 0 || x >= Screen.width || y >= Screen.height
                || !camera.pixelRect.Contains(new Vector2(x, Screen.height - y)))
                throw new Exception("screen_points use finite screenshot pixels, origin top-left, inside the camera");
            Ray ray = camera.ScreenPointToRay(new Vector3(x, Screen.height - y, 0));
            Vector3 hit = Vector3.zero;
            bool found = false;
            float previous = 0;
            for (float distance = 0; distance <= 30000; distance += 16)
            {
                Vector3 position = ray.GetPoint(distance);
                if (Mathf.Abs(position.x) > 8640 || Mathf.Abs(position.z) > 8640) continue;
                float ground = terrain.SampleRawHeightSmooth(position);
                if (position.y <= ground)
                {
                    float low = previous, high = distance;
                    for (int i = 0; i < 20; i++)
                    {
                        float middle = (low + high) * 0.5f;
                        position = ray.GetPoint(middle);
                        if (position.y > terrain.SampleRawHeightSmooth(position)) low = middle;
                        else high = middle;
                    }
                    hit = ray.GetPoint((low + high) * 0.5f);
                    found = true;
                    break;
                }
                previous = distance;
            }
            var sample = Host.Obj("name", Json.Str(point, "name", ""), "screen_top_left", new object[] { x, y },
                "ray_origin", Vec(ray.origin), "ray_direction", Vec(ray.direction), "hit", found,
                "method", "native Camera.ScreenPointToRay + TerrainManager.SampleRawHeightSmooth ray march/bisection");
            if (found)
            {
                float ground, surface;
                Vector3 velocity, normal;
                bool wet = terrain.SampleWaterData(new Vector2(hit.x, hit.z), out ground, out surface, out velocity, out normal);
                sample["world_position"] = Vec(hit);
                sample["native_terrain_height_m"] = terrain.SampleRawHeightSmooth(hit);
                sample["water"] = Host.Obj("wet", wet, "ground", ground, "surface", surface,
                    "depth_m", wet ? surface - ground : 0f, "velocity", Vec(velocity));
                sample["projected_screen_bottom_left"] = Vec(camera.WorldToScreenPoint(hit));
            }
            return sample;
        }

        static Dictionary<string, object> Observe(Dictionary<string, object> q)
        {
            var terrain = Singleton<TerrainManager>.instance;
            float treeRadius = (float)Json.Num(q, "tree_radius", 0);
            if (float.IsNaN(treeRadius) || float.IsInfinity(treeRadius) || treeRadius < 0 || treeRadius > 1000)
                throw new Exception("tree_radius must be finite and between 0 and 1000 metres");
            var samples = new List<object>();
            if (q.ContainsKey("points"))
                foreach (var item in (List<object>)q["points"])
                {
                    var point = (Dictionary<string, object>)item;
                    float x = Convert.ToSingle(point["x"]), z = Convert.ToSingle(point["z"]);
                    if (float.IsNaN(x) || float.IsInfinity(x) || float.IsNaN(z) || float.IsInfinity(z)
                        || Mathf.Abs(x) > 8640f || Mathf.Abs(z) > 8640f)
                        throw new Exception("world_observe points must be finite native world coordinates inside +/-8640m");
                    var sample = Host.Obj("name", Json.Str(point, "name", ""), "x", point["x"], "z", point["z"],
                        "sample_position", new object[] { x, 0f, z },
                        "height_m", terrain.SampleRawHeightSmooth(new Vector3(x, 0, z)));
                    if (treeRadius > 0) sample["trees"] = TreesNear(new Vector3(x, 0, z), treeRadius, terrain);
                    samples.Add(sample);
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
                "field_of_view_degrees", camera.fieldOfView, "aspect", camera.aspect,
                "pixel_width", camera.pixelWidth, "pixel_height", camera.pixelHeight,
                "screen_width", Screen.width, "screen_height", Screen.height,
                "pixel_rect", new object[] { camera.pixelRect.x, camera.pixelRect.y, camera.pixelRect.width, camera.pixelRect.height },
                "render_heading_degrees", horizontal < 0.00001f ? null : (object)Mathf.Repeat(Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg, 360f),
                "areas_visible", Singleton<GameAreaManager>.instance.AreasVisible);
            var screenSamples = new List<object>();
            if (q.ContainsKey("screen_points"))
                foreach (var item in (List<object>)q["screen_points"])
                    screenSamples.Add(ScreenSample(camera, terrain, (Dictionary<string, object>)item));
            return Host.Obj("source", "TerrainManager.SampleRawHeightSmooth/world camera", "points", samples,
                "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex, "camera", observation,
                "screen_points", screenSamples);
        }
    }
}
