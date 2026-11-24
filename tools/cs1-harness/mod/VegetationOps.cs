using System;
using System.Collections;
using System.Collections.Generic;
using ColossalFramework;
using ColossalFramework.Math;
using UnityEngine;

namespace Cs1Harness
{
    public static class VegetationOps
    {
        public static void Register()
        {
            Host.Register("vegetation_catalog", Needs.City, "loaded trees with native mesh, scale and texture metrics", Catalog);
            Host.Register("vegetation_retarget", Needs.City, "job: replace every existing tree's prefab in this disposable city: {name}", Retarget);
            Host.Register("vegetation_pair", Needs.City, "job: clear trees and place a comparison pair: {left,right,x,z,gap}", Pair);
            Host.Register("vegetation_frames", Needs.City, "job: collect uncapped wall-frame milliseconds: {frames:300}", Frames);
        }

        static Dictionary<string, object> MeshData(Mesh mesh)
        {
            if (mesh == null) return null;
            var size = mesh.bounds.size;
            return Host.Obj("triangles", mesh.isReadable ? (object)(mesh.triangles.Length / 3) : null,
                "vertices", mesh.vertexCount, "cpu_readable", mesh.isReadable,
                "renderer_bounds_size_m", new object[] { size.x, size.y, size.z });
        }

        static Dictionary<string, object> Describe(TreeInfo t)
        {
            var textures = new List<object>();
            var material = t.m_material;
            if (material != null)
                foreach (string channel in new[] { "_MainTex", "_XYCAMap", "_XYSMap", "_ACIMap" })
                {
                    if (!material.HasProperty(channel)) continue;
                    var tex = material.GetTexture(channel);
                    if (tex != null) textures.Add(Host.Obj("channel", channel, "width", tex.width, "height", tex.height));
                }
            var main = MeshData(t.m_mesh);
            if (main != null && t.m_generatedInfo != null)
            {
                var size = t.m_generatedInfo.m_size;
                main["size_m"] = new object[] { size.x, size.y, size.z };
                main["size_basis"] = "TreeInfoGen.m_size, before instance random scale";
            }
            return Host.Obj("name", t.name, "main", main, "lod", MeshData(t.m_lodMesh1),
                "textures", textures, "scale_range", new object[] { t.m_minScale, t.m_maxScale },
                "shader", material == null || material.shader == null ? null : material.shader.name,
                "lod_distance_m", t.m_lodRenderDistance,
                "vertex_color_count", t.m_mesh != null && t.m_mesh.isReadable ? (object)t.m_mesh.colors32.Length : null);
        }

        static TreeInfo Find(string name)
        {
            var info = PrefabCollection<TreeInfo>.FindLoaded(name);
            if (info == null) throw new ArgumentException("No loaded tree: " + name);
            return info;
        }

        static Dictionary<string, object> Catalog(Dictionary<string, object> q)
        {
            var result = new List<object>();
            for (uint i = 0; i < PrefabCollection<TreeInfo>.LoadedCount(); i++)
            {
                var tree = PrefabCollection<TreeInfo>.GetLoaded(i);
                if (tree != null) result.Add(Describe(tree));
            }
            var manager = Singleton<TreeManager>.instance;
            var bins = new Dictionary<int, int>();
            int best = 0, maximum = 0;
            for (uint i = 1; i < manager.m_trees.m_buffer.Length; i++)
                if ((manager.m_trees.m_buffer[i].m_flags & (ushort)TreeInstance.Flags.Created) != 0)
                {
                    var p = manager.m_trees.m_buffer[i].Position;
                    // Outer decorative forest can be outside vanilla's rendered
                    // terrain despite valid terrain-ray hits. Keep both zooms
                    // safely in the interior, then verify actual frame pixels.
                    if (Math.Abs(p.x) > 3500 || Math.Abs(p.z) > 3500) continue;
                    int key = Mathf.Clamp((int)((p.x + 8640) / 540), 0, 31) + 32 * Mathf.Clamp((int)((p.z + 8640) / 540), 0, 31);
                    int value;
                    bins.TryGetValue(key, out value);
                    bins[key] = ++value;
                    if (value > maximum) { maximum = value; best = key; }
                }
            if (maximum == 0) throw new InvalidOperationException("No interior forest patch found");
            return Host.Obj("trees", result, "instances", manager.m_treeCount,
                "forest_patch", new object[] { (best % 32) * 540 - 8370, (best / 32) * 540 - 8370 }, "patch_trees", maximum);
        }

        static Dictionary<string, object> Retarget(Dictionary<string, object> q)
        {
            var info = Find(Json.Str(q, "name", ""));
            var job = Jobs.Start("vegetation_retarget", j => RetargetSteps(j, info));
            return Host.Obj("job", job.Id);
        }

        static IEnumerator RetargetSteps(Job job, TreeInfo info)
        {
            bool done = false;
            int count = 0;
            Singleton<SimulationManager>.instance.SimulationPaused = true;
            Singleton<SimulationManager>.instance.AddAction(() =>
            {
                var manager = Singleton<TreeManager>.instance;
                for (uint i = 1; i < manager.m_trees.m_buffer.Length; i++)
                    if ((manager.m_trees.m_buffer[i].m_flags & (ushort)TreeInstance.Flags.Created) != 0)
                    {
                        manager.m_trees.m_buffer[i].Info = info;
                        manager.UpdateTree(i);
                        count++;
                    }
                done = true;
            });
            yield return Jobs.Until(() => done, 60, "retarget trees");
            job.Result["instances"] = count;
            job.Result["name"] = info.name;
        }

        static Dictionary<string, object> Pair(Dictionary<string, object> q)
        {
            var left = Find(Json.Str(q, "left", ""));
            var right = Find(Json.Str(q, "right", ""));
            float x = (float)Json.Num(q, "x", 0), z = (float)Json.Num(q, "z", 0);
            float gap = (float)Json.Num(q, "gap", 30);
            if (gap <= 0 || gap > 300 || Math.Abs(x) > 8000 || Math.Abs(z) > 8000)
                throw new ArgumentException("Invalid specimen position/gap");
            var job = Jobs.Start("vegetation_pair", j => PairSteps(j, left, right, x, z, gap));
            return Host.Obj("job", job.Id);
        }

        static IEnumerator PairSteps(Job job, TreeInfo left, TreeInfo right, float x, float z, float gap)
        {
            bool done = false;
            var created = new List<object>();
            Singleton<SimulationManager>.instance.SimulationPaused = true;
            Singleton<SimulationManager>.instance.AddAction(() =>
            {
                var manager = Singleton<TreeManager>.instance;
                for (uint i = 1; i < manager.m_trees.m_buffer.Length; i++)
                    if ((manager.m_trees.m_buffer[i].m_flags & (ushort)TreeInstance.Flags.Created) != 0)
                        manager.ReleaseTree(i);
                var random = new Randomizer(1326);
                int index = 0;
                foreach (var info in new[] { left, right })
                {
                    var pos = new Vector3(x + (index++ == 0 ? -gap / 2 : gap / 2), 0, z);
                    pos.y = Singleton<TerrainManager>.instance.SampleRawHeightSmooth(pos);
                    uint id;
                    bool ok = manager.CreateTree(out id, ref random, info, pos, true);
                    if (ok) { manager.m_trees.m_buffer[id].GrowState = 15; manager.UpdateTree(id); }
                    created.Add(Host.Obj("name", info.name, "created", ok, "id", id,
                        "position", new object[] { pos.x, pos.y, pos.z }));
                }
                done = true;
            });
            yield return Jobs.Until(() => done, 60, "place specimen pair");
            job.Result["specimens"] = created;
        }

        static Dictionary<string, object> Frames(Dictionary<string, object> q)
        {
            int n = (int)Json.Num(q, "frames", 300);
            if (n < 60 || n > 3000) throw new ArgumentException("frames must be 60..3000");
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            var job = Jobs.Start("vegetation_frames", j => FrameSteps(j, n));
            return Host.Obj("job", job.Id);
        }

        static IEnumerator FrameSteps(Job job, int n)
        {
            yield return Jobs.Frames(120);
            var values = new List<object>();
            double last = Time.realtimeSinceStartup;
            for (int i = 0; i < n; i++)
            {
                yield return null;
                double now = Time.realtimeSinceStartup;
                values.Add((now - last) * 1000);
                last = now;
            }
            job.Result["frame_ms"] = values;
            job.Result["instances"] = Singleton<TreeManager>.instance.m_treeCount;
        }
    }
}
