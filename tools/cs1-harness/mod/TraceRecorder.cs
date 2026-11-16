#if TRACE_OBSERVER
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;

namespace Cs1Harness
{
    // Every write here targets this observer's preallocated storage, never game data.
    public static class TraceRecorder
    {
        const int MaxSteps = 512, MaxNodes = 512, MaxTouched = 32;
        static int SourceCount, stepLimit;
        static int[] TargetIds, ExtraPositions;
        public static Dictionary<string, object> Configuration;
        static readonly FieldInfo Buffers = Field("m_waterBuffers"), Floors = Field("m_heightBuffer"),
            WaterFrame = Field("m_waterFrameIndex"), WaterFrame2 = Field("m_waterFrameIndex2"),
            SimFrame = Field("m_simulationFrameIndex"), Step = Field("m_stepIndex");
        static Transaction[] records;
        [ThreadStatic] static Transaction current;
        static bool capturing, initialized;
        static int active, count, nodes, touched;
        static int[] positions = new int[MaxNodes], slots;
        static WaterSource[] controls, expected;
        static WaterSimulation owner;
        public static string Error;
        public static bool HitBound;
        public static int Active { get { return active; } }

        sealed class Transaction
        {
            public uint Water, Water2, Sim, Step, EndWater, PublishedWater, PublishedWater2;
            public int Working, BeforeCount, AfterCount;
            public bool HasB, HasE, Left;
            public ushort[] PublishedEnd = new ushort[MaxNodes * 4];
            public ushort[][] Snapshots = new ushort[3 + MaxTouched * 3][];
            public WaterSource[] Pre = new WaterSource[MaxTouched], Input = new WaterSource[MaxTouched],
                Final = new WaterSource[MaxTouched], Committed = new WaterSource[MaxTouched];
            public int[] Availability = new int[MaxTouched], Nominal = new int[MaxTouched];
            public bool[] InputSeen = new bool[MaxTouched], AfterSeen = new bool[MaxTouched];
            public Transaction()
            {
                for (int i = 0; i < Snapshots.Length; i++) Snapshots[i] = new ushort[MaxNodes * 4];
            }
        }

        static FieldInfo Field(string name)
        {
            var field = typeof(WaterSimulation).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null) throw new MissingFieldException("WaterSimulation", name);
            return field;
        }
        static uint U(FieldInfo field, WaterSimulation water) { return Convert.ToUInt32(field.GetValue(water)); }
        static void Fail(Exception error) { if (Error == null) Error = error.GetType().Name + ": " + error.Message; capturing = false; }

        static UnityEngine.Vector3 Vector(object value)
        {
            var a = (List<object>)value;
            if (a.Count != 3) throw new Exception("source vector must have three components");
            return new UnityEngine.Vector3(Convert.ToSingle(a[0]), Convert.ToSingle(a[1]), Convert.ToSingle(a[2]));
        }
        public static void Arm(Dictionary<string, object> request)
        {
            if (records != null) throw new Exception("one trace only per disposable process");
            var catalog = (List<object>)request["controls"];
            SourceCount = catalog.Count;
            if (SourceCount < 1 || SourceCount > 4096) throw new Exception("trace source count must be 1..4096");
            expected = new WaterSource[SourceCount]; controls = new WaterSource[SourceCount]; slots = new int[SourceCount];
            for (int i = 0; i < SourceCount; i++)
            {
                var row = (Dictionary<string, object>)catalog[i];
                expected[i].m_type = Convert.ToUInt16(row["type"]); expected[i].m_target = Convert.ToUInt16(row["target"]);
                expected[i].m_inputPosition = Vector(row["input"]); expected[i].m_outputPosition = Vector(row["output"]);
                expected[i].m_inputRate = Convert.ToUInt32(row["input_rate"]); expected[i].m_outputRate = Convert.ToUInt32(row["output_rate"]);
                if (expected[i].m_type != 1) throw new Exception("this observer version accepts natural type1 catalogs only");
            }
            var targets = (List<object>)request["sources"]; TargetIds = new int[targets.Count];
            for (int i = 0; i < targets.Count; i++)
            {
                TargetIds[i] = Convert.ToInt32(targets[i]);
                if (TargetIds[i] < 1 || TargetIds[i] > SourceCount) throw new Exception("trace source ID out of range");
            }
            var cells = (List<object>)request["cells"]; ExtraPositions = new int[cells.Count];
            for (int i = 0; i < cells.Count; i++)
            {
                var pair = (List<object>)cells[i];
                if (pair.Count != 2) throw new Exception("trace cell requires x,z");
                double x = Convert.ToDouble(pair[0]), z = Convert.ToDouble(pair[1]);
                if (x < -8640 || x > 8640 || z < -8640 || z > 8640 || x % 16 != 0 || z % 16 != 0)
                    throw new Exception("trace cells must be native 16m grid nodes");
                ExtraPositions[i] = ((int)z + 8640) / 16 * 1081 + ((int)x + 8640) / 16;
            }
            if (TargetIds.Length + ExtraPositions.Length == 0 || TargetIds.Length > MaxTouched || ExtraPositions.Length > MaxNodes)
                throw new Exception("empty or oversized trace region");
            stepLimit = (int)Json.Num(request, "max_steps", MaxSteps);
            if (stepLimit < 1 || stepLimit > MaxSteps) throw new Exception("trace max_steps must be 1..512");
            Configuration = Obj("sources", TargetIds, "cells", cells, "max_steps", stepLimit, "binding", request["binding"]);
            records = new Transaction[stepLimit];
            for (int i = 0; i < stepLimit; i++) records[i] = new Transaction();
            for (int i = 0; i < SourceCount; i++) slots[i] = -1;
            capturing = true;
        }
        public static void Stop() { capturing = false; }

        static bool Inside(int index, UnityEngine.Vector3 position, uint rate)
        {
            if (rate == 0) return false;
            float r = (float)Math.Sqrt((float)rate) * .4f + 10f;
            float dx = index % 1081 * 16 - 8640 - position.x;
            float dz = index / 1081 * 16 - 8640 - position.z;
            return dx * dx + dz * dz < r * r;
        }
        static bool SameControl(WaterSource a, WaterSource b)
        {
            return a.m_type == b.m_type && a.m_target == b.m_target && a.m_inputRate == b.m_inputRate &&
                a.m_outputRate == b.m_outputRate && a.m_inputPosition.x == b.m_inputPosition.x &&
                a.m_inputPosition.y == b.m_inputPosition.y && a.m_inputPosition.z == b.m_inputPosition.z &&
                a.m_outputPosition.x == b.m_outputPosition.x && a.m_outputPosition.y == b.m_outputPosition.y && a.m_outputPosition.z == b.m_outputPosition.z;
        }
        static void Initialize(WaterSimulation water)
        {
            var set = new HashSet<int>();
            foreach (int p in ExtraPositions) set.Add(p);
            foreach (int id in TargetIds)
            {
                var s = water.m_waterSources.m_buffer[id - 1];
                for (int direction = 0; direction < 2; direction++)
                {
                    uint rate = direction == 0 ? s.m_inputRate : s.m_outputRate;
                    if (rate == 0) continue;
                    var p = direction == 0 ? s.m_inputPosition : s.m_outputPosition;
                    float r = (float)Math.Sqrt((float)rate) * .4f + 10f;
                    int cx = (int)Math.Round((p.x + 8640) / 16), cz = (int)Math.Round((p.z + 8640) / 16);
                    int reach = (int)Math.Ceiling(r / 16) + 1;
                    for (int z = Math.Max(0, cz - reach); z <= Math.Min(1080, cz + reach); z++)
                        for (int x = Math.Max(0, cx - reach); x <= Math.Min(1080, cx + reach); x++)
                            if (Inside(z * 1081 + x, p, rate))
                                for (int dz = -1; dz <= 1; dz++) for (int dx = -1; dx <= 1; dx++)
                                    if (x + dx >= 0 && x + dx <= 1080 && z + dz >= 0 && z + dz <= 1080)
                                    {
                                        set.Add((z + dz) * 1081 + x + dx);
                                        if (set.Count > MaxNodes) throw new Exception("trace node bound exceeded");
                                    }
                }
            }
            if (set.Count > MaxNodes) throw new Exception("trace node bound exceeded");
            var ordered = new List<int>(set); ordered.Sort(); nodes = ordered.Count; ordered.CopyTo(positions);
            Array.Copy(water.m_waterSources.m_buffer, controls, SourceCount);
            for (int i = 0; i < SourceCount; i++)
            {
                slots[i] = -1;
                var s = controls[i];
                for (int n = 0; n < nodes; n++)
                    if (Inside(positions[n], s.m_inputPosition, s.m_inputRate) || Inside(positions[n], s.m_outputPosition, s.m_outputRate))
                    { if (touched >= MaxTouched) throw new Exception("trace source bound exceeded"); slots[i] = touched++; break; }
            }
            owner = water; initialized = true;
        }
        static void Copy(WaterSimulation water, ushort[] destination, bool published)
        {
            var buffers = (WaterSimulation.Cell[][])Buffers.GetValue(water);
            var floor = (ushort[])Floors.GetValue(water);
            if (ReferenceEquals(destination, floor)) throw new Exception("observer destination aliases native floor");
            int buffer = published ? 1 - (int)((U(WaterFrame, water) >> 6) & 1) : current.Working;
            for (int n = 0; n < nodes; n++)
            {
                int p = positions[n]; var cell = buffers[buffer][p];
                destination[n * 4] = cell.m_height;
                destination[n * 4 + 1] = floor[p];
                destination[n * 4 + 2] = unchecked((ushort)cell.m_velocityX);
                destination[n * 4 + 3] = unchecked((ushort)cell.m_velocityZ);
            }
        }

        public static void Begin(WaterSimulation water)
        {
            Interlocked.Increment(ref active);
            try
            {
                current = null;
                if (!capturing || water.m_waterSources.m_size != SourceCount) return;
                for (int i = 0; i < SourceCount; i++)
                    if (!SameControl(expected[i], water.m_waterSources.m_buffer[i])) throw new Exception("loaded source catalog differs from explicit trace binding");
                if (!initialized) Initialize(water);
                if (!ReferenceEquals(owner, water)) throw new Exception("water instance changed");
                if (count >= stepLimit) { HitBound = true; capturing = false; return; }
                current = records[count++];
                current.Water = U(WaterFrame, water); current.Water2 = U(WaterFrame2, water);
                current.Sim = U(SimFrame, water); current.Step = U(Step, water);
                current.Working = (int)((current.Water >> 6) & 1);
                Copy(water, current.Snapshots[0], true);
                for (int i = 0; i < SourceCount; i++)
                    if (!SameControl(controls[i], water.m_waterSources.m_buffer[i])) throw new Exception("encoded forcing changed");
            }
            catch (Exception e) { Fail(e); }
        }
        public static void SourceBefore(WaterSimulation water, int index)
        {
            try
            {
                if (current == null || Error != null) return;
                if (index != current.BeforeCount++) throw new Exception("source order changed");
                if (index == 0) { Copy(water, current.Snapshots[1], false); current.HasB = true; }
                int slot = slots[index]; if (slot < 0) return;
                current.Pre[slot] = water.m_waterSources.m_buffer[index];
                Copy(water, current.Snapshots[3 + slot * 3], false);
            }
            catch (Exception e) { Fail(e); }
        }
        public static void AfterInput(WaterSimulation water, int index, WaterSource source, int availability, int nominal)
        {
            try
            {
                if (current == null || Error != null) return;
                int slot = slots[index]; if (slot < 0) return;
                current.Input[slot] = source; current.Availability[slot] = availability; current.Nominal[slot] = nominal;
                current.InputSeen[slot] = true;
                Copy(water, current.Snapshots[4 + slot * 3], false);
            }
            catch (Exception e) { Fail(e); }
        }
        public static void SourceAfter(WaterSimulation water, int index, WaterSource source)
        {
            try
            {
                if (current == null || Error != null) return;
                if (index != current.AfterCount++) throw new Exception("source completion order changed");
                int slot = slots[index]; if (slot < 0) return;
                current.Final[slot] = source; current.Committed[slot] = water.m_waterSources.m_buffer[index];
                current.AfterSeen[slot] = true;
                Copy(water, current.Snapshots[5 + slot * 3], false);
            }
            catch (Exception e) { Fail(e); }
        }
        public static void BeforePublish(WaterSimulation water)
        {
            try
            {
                if (current == null || Error != null) return;
                Copy(water, current.Snapshots[2], false); current.HasE = true;
                current.EndWater = U(WaterFrame, water);
            }
            catch (Exception e) { Fail(e); }
        }
        public static void Leave(WaterSimulation water)
        {
            try
            {
                if (current != null)
                {
                    current.PublishedWater = U(WaterFrame, water); current.PublishedWater2 = U(WaterFrame2, water);
                    Copy(water, current.PublishedEnd, true); current.Left = true;
                }
                current = null;
            }
            catch (Exception e) { Fail(e); }
            finally { Interlocked.Decrement(ref active); }
        }

        static Dictionary<string, object> Obj(params object[] pairs)
        { var result = new Dictionary<string, object>(); for (int i = 0; i < pairs.Length; i += 2) result[(string)pairs[i]] = pairs[i + 1]; return result; }
        static object Source(WaterSource s)
        { return Obj("type", s.m_type, "input", new[] {s.m_inputPosition.x,s.m_inputPosition.y,s.m_inputPosition.z},
            "output", new[] {s.m_outputPosition.x,s.m_outputPosition.y,s.m_outputPosition.z}, "target", s.m_target,
            "input_rate", s.m_inputRate, "output_rate", s.m_outputRate, "water", s.m_water, "flow", s.m_flow, "pollution", s.m_pollution); }
        static ushort[] Snapshot(Transaction r, int phase)
        { var copy = new ushort[nodes * 4]; Array.Copy(r.Snapshots[phase], copy, copy.Length); return copy; }

        public static Dictionary<string, object> Export(string directory, bool unpatched)
        {
            if (capturing || active != 0) throw new Exception("trace must be stopped and idle before writing");
            Directory.CreateDirectory(directory);
            var sourceRows = new List<object>();
            for (int i = 0; i < SourceCount; i++) if (slots[i] >= 0) sourceRows.Add(Obj("id", i + 1, "slot", slots[i], "control", Source(controls[i])));
            var nodeRows = new List<object>(); for (int n = 0; n < nodes; n++) nodeRows.Add(new[] {positions[n] % 1081 * 16 - 8640, positions[n] / 1081 * 16 - 8640});
            var header = Obj("kind", "header", "engine", TraceIL.Engine, "proof", TraceIL.Proof, "nodes", nodeRows,
                "source_count", SourceCount, "sources", sourceRows, "targets", TargetIds,
                "packing", new[] {"depth_u16", "native_floor_u16", "velocity_x_i16_reinterpreted_u16", "velocity_z_i16_reinterpreted_u16"},
                "steps", count, "max_steps", stepLimit, "error", Error, "hit_bound", HitBound, "unpatched", unpatched,
                "configuration", Configuration);
            int complete = 0;
            string path = Path.Combine(directory, "trace.jsonl");
            using (var writer = new StreamWriter(path, false, new UTF8Encoding(false)))
            {
                writer.WriteLine(Json.Write(header));
                for (int t = 0; t < count; t++)
                {
                    var r = records[t]; var sources = new List<object>(); bool ok = r.HasB && r.HasE && r.Left && r.BeforeCount == SourceCount && r.AfterCount == SourceCount;
                    for (int i = 0; i < SourceCount; i++) if (slots[i] >= 0)
                    {
                        int slot = slots[i]; ok &= r.InputSeen[slot] && r.AfterSeen[slot];
                        sources.Add(Obj("id", i + 1, "before", Source(r.Pre[slot]), "input", Source(r.Input[slot]),
                            "after", Source(r.Final[slot]), "committed", Source(r.Committed[slot]),
                            "availability", r.Availability[slot], "nominal", r.Nominal[slot],
                            "pre_cells", Snapshot(r, 3 + slot * 3), "input_cells", Snapshot(r, 4 + slot * 3), "post_cells", Snapshot(r, 5 + slot * 3)));
                    }
                    if (ok) complete++;
                    writer.WriteLine(Json.Write(Obj("kind", "transaction", "index", t, "water_frame", r.Water, "water_frame2", r.Water2,
                        "simulation_frame", r.Sim, "step", r.Step, "end_water_frame", r.EndWater, "working_buffer", r.Working,
                        "published_water_frame", r.PublishedWater, "published_water_frame2", r.PublishedWater2,
                        "published_buffer", 1 - (int)((r.PublishedWater >> 6) & 1), "published_end", r.PublishedEnd,
                        "source_commit_expected", r.Water < r.EndWater, "complete", ok,
                        "published", Snapshot(r, 0), "transport", Snapshot(r, 1), "end", Snapshot(r, 2), "sources", sources)));
                }
            }
            return Obj("path", path, "steps", count, "complete_steps", complete, "nodes", nodes, "touched_sources", touched,
                "error", Error, "hit_bound", HitBound, "unpatched", unpatched, "proof", TraceIL.Proof,
                "complete", Error == null && !HitBound && count > 0 && complete == count && unpatched);
        }
    }
}
#endif
