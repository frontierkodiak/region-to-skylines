using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using ColossalFramework;
using UnityEngine;

namespace Cs1Harness
{
    // Optional observation only: no hooks, field writes or forcing changes.
    public static class WaterStudyOps
    {
        public static void Register()
        {
            Host.Register("water_study_snapshot", Needs.City, "fresh full depth/floor/probe/control snapshot with clock brackets: {dir,prefix,points}", Snapshot);
            Host.Register("water_study_runtime", Needs.City, "loaded module metadata/current location hashes, NOT loaded-image identity", q => RuntimeMetadata());
        }

        static object Clocks(WaterSimulation water)
        {
            var fields = new Dictionary<string, object>();
            foreach (var name in new[] { "m_waterFrameIndex", "m_waterFrameIndex2", "m_simulationFrameIndex", "m_stepIndex" })
            {
                try
                {
                    var field = typeof(WaterSimulation).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                    if (field == null) throw new MissingFieldException("WaterSimulation", name);
                    fields[name] = Host.Obj("available", true, "value", Convert.ToUInt32(field.GetValue(water)));
                }
                catch (Exception error) { fields[name] = Host.Obj("available", false, "error", error.GetType().Name + ": " + error.Message); }
            }
            return Host.Obj("simulation_frame", Singleton<SimulationManager>.instance.m_currentFrameIndex,
                "water_fields", fields, "semantics", "Named runtime counters, not an evaporation period or physical flux unit");
        }

        static string Hash(byte[] bytes)
        {
            using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }

        static Dictionary<string, object> Write(string dir, string prefix, string name, byte[] bytes)
        {
            string path = Path.Combine(dir, prefix + "-" + name + ".u16");
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
                stream.Write(bytes, 0, bytes.Length);
            return Host.Obj("path", path, "bytes", bytes.Length, "sha256", Hash(bytes));
        }

        static byte[] Bytes(ushort[] values)
        {
            byte[] bytes = new byte[values.Length * 2];
            Buffer.BlockCopy(values, 0, bytes, 0, bytes.Length);
            return bytes;
        }

        static Dictionary<string, object> Snapshot(Dictionary<string, object> q)
        {
            string dir = Json.Str(q, "dir", ""), prefix = Json.Str(q, "prefix", "");
            if (!Path.IsPathRooted(dir) || prefix.Length < 1 || prefix.Length > 64)
                throw new Exception("water study needs an absolute dir and a unique short prefix");
            foreach (char c in prefix)
                if (!(c >= 'a' && c <= 'z') && !(c >= '0' && c <= '9') && c != '_' && c != '-')
                    throw new Exception("water study prefix must contain only lowercase ASCII letters, digits, '_' or '-'");
            Directory.CreateDirectory(dir);
            foreach (string name in new[] { "water", "terrain", "water-ground", "water-ground-target" })
                if (File.Exists(Path.Combine(dir, prefix + "-" + name + ".u16")))
                    throw new Exception("water study refuses to overwrite an existing snapshot: " + prefix);
            var terrain = Singleton<TerrainManager>.instance;
            var water = terrain.WaterSimulation;
            object before = Clocks(water);
            var points = new List<object>();
            if (q.ContainsKey("points"))
                foreach (var item in (List<object>)q["points"])
                {
                    var raw = (List<object>)item;
                    if (raw.Count != 2) throw new Exception("water study points require x,z");
                    float x = Convert.ToSingle(raw[0]), z = Convert.ToSingle(raw[1]);
                    if (float.IsNaN(x) || float.IsInfinity(x) || float.IsNaN(z) || float.IsInfinity(z) || Mathf.Abs(x) > 8640 || Mathf.Abs(z) > 8640)
                        throw new Exception("water study point outside finite native square");
                    float ground, surface; Vector3 velocity, normal;
                    bool wet = terrain.SampleWaterData(new Vector2(x, z), out ground, out surface, out velocity, out normal);
                    points.Add(Host.Obj("x", x, "z", z, "ground", ground, "surface", surface,
                        "depth", wet ? surface - ground : 0f, "wet", wet,
                        "velocity", new object[] { velocity.x, velocity.y, velocity.z }));
                }
            var controls = new List<object>();
            for (int i = 0; i < water.m_waterSources.m_size; i++)
            {
                var s = water.m_waterSources.m_buffer[i];
                if (s.m_type == 0) continue;
                controls.Add(Host.Obj("id", i + 1, "type", s.m_type,
                    "input_position", new object[] { s.m_inputPosition.x, s.m_inputPosition.y, s.m_inputPosition.z },
                    "output_position", new object[] { s.m_outputPosition.x, s.m_outputPosition.y, s.m_outputPosition.z },
                    "target_fixed", s.m_target, "input_rate", s.m_inputRate, "output_rate", s.m_outputRate,
                    "flow_raw", s.m_flow, "buffered_water_raw", s.m_water));
            }
            var cells = water.BeginRead();
            byte[] depths = new byte[cells.Length * 2], rawTerrain, floors, targets;
            long sum = 0, wetNodes = 0;
            try
            {
                for (int i = 0; i < cells.Length; i++)
                {
                    int height = cells[i].m_height;
                    depths[2 * i] = (byte)(height & 255); depths[2 * i + 1] = (byte)(height >> 8);
                    sum += height; if (height > 0) wetNodes++;
                }
                foreach (Dictionary<string, object> p in points)
                {
                    float px = Convert.ToSingle(p["x"]), pz = Convert.ToSingle(p["z"]);
                    int cx = Mathf.RoundToInt((px + 8640) / 16), cz = Mathf.RoundToInt((pz + 8640) / 16), maximum = 0;
                    for (int z = Mathf.Max(0, cz - 4); z <= Mathf.Min(1080, cz + 4); z++)
                        for (int x = Mathf.Max(0, cx - 4); x <= Mathf.Min(1080, cx + 4); x++)
                        {
                            float dx = x * 16 - 8640 - px, dz = z * 16 - 8640 - pz;
                            if (dx * dx + dz * dz <= 4096) maximum = Mathf.Max(maximum, cells[z * 1081 + x].m_height);
                        }
                    p["max_depth_within_64m"] = maximum / 64f;
                }
                rawTerrain = Bytes(terrain.RawHeights);
                floors = Bytes(terrain.BlockHeights);
                targets = Bytes(terrain.BlockHeightTargets);
            }
            finally { water.EndRead(); }
            object after = Clocks(water);
            var files = Host.Obj("water", Write(dir, prefix, "water", depths),
                "terrain", Write(dir, prefix, "terrain", rawTerrain),
                "water-ground", Write(dir, prefix, "water-ground", floors),
                "water-ground-target", Write(dir, prefix, "water-ground-target", targets));
            return Host.Obj("schema", "polli.water-study-snapshot/1", "prefix", prefix,
                "before", before, "after", after, "files", files, "samples", points, "sources", controls,
                "depth_sum_q", sum, "wet_nodes", wetNodes, "cells", cells.Length,
                "scope", "Probe API, grid and source reads are bracketed, not proven atomic. Named counters and depth sums do not establish integrated flux units.");
        }

        static Dictionary<string, object> RuntimeMetadata()
        {
            var modules = new List<object>();
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                var row = Host.Obj("name", assembly.FullName);
                try
                {
                    row["module_version_id"] = assembly.ManifestModule.ModuleVersionId.ToString();
                    row["location"] = assembly.Location;
                    row["current_location_sha256"] = File.Exists(assembly.Location) ? Hash(File.ReadAllBytes(assembly.Location)) : null;
                }
                catch (Exception error) { row["error"] = error.GetType().Name + ": " + error.Message; }
                modules.Add(row);
            }
            return Host.Obj("schema", "polli.water-study-runtime-metadata/1", "modules", modules,
                "scope", "Loaded-module metadata and current on-disk location bytes only. NOT complete loaded-image/JIT identity or runtime health.");
        }
    }
}
