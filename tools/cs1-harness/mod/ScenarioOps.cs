using System;
using System.Collections.Generic;
using ColossalFramework;
using ColossalFramework.Math;
using UnityEngine;

namespace Cs1Harness
{
    // Disposable New Game fixture. All construction runs on the simulation thread;
    // NetTool/BuildingTool enforce the same space, slope, area and money rules as play.
    public static class ScenarioOps
    {
        const float Spacing = 96f;
        const float Half = Spacing * 1.5f;
        const float MaximumApproachDot = 0.64f;
        static string city;
        static volatile string state = "idle";
        static string error;
        static Dictionary<string, object> result;
        static readonly List<ushort> roads = new List<ushort>();
        static readonly List<ushort> buildings = new List<ushort>();
        static readonly List<uint> paths = new List<uint>();
        static readonly List<Dictionary<string, object>> pathResults = new List<Dictionary<string, object>>();
        static readonly List<string> pathDirections = new List<string>();
        static readonly List<PathUnit.Position> pathEdges = new List<PathUnit.Position>();
        static Vector3 center;

        sealed class PlacementRejected : Exception
        {
            public readonly ToolBase.ToolErrors Errors;
            public PlacementRejected(string context, ToolBase.ToolErrors errors) : base(context + ": " + errors)
            { Errors = errors; }
        }

        public static void Register()
        {
            Host.Register("scenario_build", Needs.City, "build test-city in a fresh, paused New Game; poll scenario_status", Start);
            Host.Register("scenario_status", Needs.City, "construction and live utility state (inspect:true lists hookup nodes and water prefabs)", Status);
            Host.Register("scenario_paths", Needs.City, "native car paths between the fixture and highway edges: {start:true}, then poll", Paths);
        }

        static Vector3 Ground(float x, float z)
        {
            var p = new Vector3(x, 0, z);
            p.y = Singleton<TerrainManager>.instance.SampleRawHeightSmooth(p);
            return p;
        }

        static object[] XYZ(Vector3 p) { return new object[] { p.x, p.y, p.z }; }

        static bool Inside(Vector3 p, float margin = 32f)
        {
            int x, z;
            Singleton<GameAreaManager>.instance.GetStartTile(out x, out z);
            return Mathf.Abs(p.x - (x - 2) * 1920f) < 960f - margin
                && Mathf.Abs(p.z - (z - 2) * 1920f) < 960f - margin;
        }

        // Exit/on-ramp stub pairs in the start tile, closest pairs first.
        static List<List<ushort>> HookupPairs()
        {
            var net = Singleton<NetManager>.instance;
            var arrive = new List<ushort>();
            var leave = new List<ushort>();
            for (int i = 1; i < net.m_nodes.m_buffer.Length; i++)
            {
                var n = net.m_nodes.m_buffer[i];
                if ((n.m_flags & (NetNode.Flags.Created | NetNode.Flags.Deleted | NetNode.Flags.Outside)) != NetNode.Flags.Created
                    || n.Info == null || !(n.Info.m_netAI is RoadBaseAI) || n.CountSegments() != 1
                    || Singleton<GameAreaManager>.instance.PointOutOfArea(n.m_position))
                    continue;
                bool inFlag = (n.m_flags & NetNode.Flags.OneWayIn) != 0, outFlag = (n.m_flags & NetNode.Flags.OneWayOut) != 0;
                if (inFlag && !outFlag) arrive.Add((ushort)i);
                if (outFlag && !inFlag) leave.Add((ushort)i);
            }
            var pairs = new List<KeyValuePair<float, List<ushort>>>();
            foreach (ushort a in arrive)
                foreach (ushort b in leave)
                    pairs.Add(new KeyValuePair<float, List<ushort>>(
                        VectorUtils.LengthXZ(net.m_nodes.m_buffer[a].m_position - net.m_nodes.m_buffer[b].m_position),
                        new List<ushort> { a, b }));
            pairs.Sort((x, y) => x.Key.CompareTo(y.Key));
            var result = new List<List<ushort>>();
            // Bound the expensive grid searches by feasible joins, not the first
            // twelve raw pairs: overlapping fragments can create many tiny gaps.
            foreach (var p in pairs)
            {
                if (!JoinLinksClear(p.Value)) continue;
                result.Add(p.Value);
                if (result.Count >= 12) break;
            }
            return result;
        }

        static List<ushort> Hookups()
        {
            var net = Singleton<NetManager>.instance;
            var ends = new List<ushort>();
            var nodes = new List<ushort>();
            for (int i = 1; i < net.m_nodes.m_buffer.Length; i++)
            {
                var n = net.m_nodes.m_buffer[i];
                if ((n.m_flags & (NetNode.Flags.Created | NetNode.Flags.Deleted | NetNode.Flags.Outside)) != NetNode.Flags.Created
                    || n.Info == null || !(n.Info.m_netAI is RoadBaseAI)
                    || Singleton<GameAreaManager>.instance.PointOutOfArea(n.m_position))
                    continue;
                nodes.Add((ushort)i);
                if (n.CountSegments() == 1)
                    ends.Add((ushort)i);
            }
            var chosen = ends.Count != 0 ? ends : nodes;
            chosen.Sort((a, b) => net.m_nodes.m_buffer[a].m_position.sqrMagnitude.CompareTo(net.m_nodes.m_buffer[b].m_position.sqrMagnitude));
            if (chosen.Count == 0)
                throw new Exception("no road hookup node in the start tile; map needs an accessible highway connection");
            // Real interchanges leave one-way ramp stubs: join the nearest stub that
            // traffic arrives on and the nearest it leaves by, so both directions work.
            if (ends.Count > 2)
            {
                // The closest pair of one exit stub and one on-ramp stub: one
                // interchange, so the hookup doesn't run between interchanges.
                ushort arrive = 0, leave = 0;
                float best = float.MaxValue;
                foreach (ushort a in chosen)
                {
                    var fa = net.m_nodes.m_buffer[a].m_flags;
                    if ((fa & NetNode.Flags.OneWayIn) == 0 || (fa & NetNode.Flags.OneWayOut) != 0) continue;
                    foreach (ushort b in chosen)
                    {
                        var fb = net.m_nodes.m_buffer[b].m_flags;
                        if ((fb & NetNode.Flags.OneWayOut) == 0 || (fb & NetNode.Flags.OneWayIn) != 0) continue;
                        float d = VectorUtils.LengthXZ(net.m_nodes.m_buffer[a].m_position - net.m_nodes.m_buffer[b].m_position);
                        if (d < best) { best = d; arrive = a; leave = b; }
                    }
                }
                if (arrive != 0 && leave != 0)
                    return new List<ushort> { arrive, leave };
            }
            // A vanilla interchange has two one-way ends. A through-road map can
            // instead be joined at existing nodes, without replacing its network.
            if (chosen.Count > 2)
                chosen.RemoveRange(2, chosen.Count - 2);
            return chosen;
        }

        static List<object> HookupInfo()
        {
            int x, z;
            var area = Singleton<GameAreaManager>.instance;
            area.GetStartTile(out x, out z);
            var tile = new Vector3((x - 2) * 1920, 0, (z - 2) * 1920);
            var net = Singleton<NetManager>.instance;
            var ids = new List<ushort>();
            for (int i = 1; i < net.m_nodes.m_buffer.Length; i++)
            {
                var n = net.m_nodes.m_buffer[i];
                if ((n.m_flags & (NetNode.Flags.Created | NetNode.Flags.Deleted)) == NetNode.Flags.Created
                    && n.Info != null && n.Info.m_netAI is RoadBaseAI) ids.Add((ushort)i);
            }
            ids.Sort((a, b) => (net.m_nodes.m_buffer[a].m_position - tile).sqrMagnitude
                .CompareTo((net.m_nodes.m_buffer[b].m_position - tile).sqrMagnitude));
            var rows = new List<object>();
            foreach (ushort id in ids.GetRange(0, Math.Min(12, ids.Count)))
            {
                var n = net.m_nodes.m_buffer[id];
                rows.Add(Host.Obj("node", id, "position", XYZ(n.m_position), "prefab", n.Info.name,
                    "segments", n.CountSegments(), "flags", n.m_flags.ToString(),
                    "out_of_area", area.PointOutOfArea(n.m_position), "elevation", n.m_elevation,
                    "base_height", n.Info.m_buildHeight,
                    "ground", Singleton<TerrainManager>.instance.SampleRawHeightSmooth(n.m_position)));
            }
            return rows;
        }

        // Where the hookup road meets the ramp stubs before running to the grid.
        static bool JoinPoint(List<ushort> hooks, out Vector3 mean, out Vector3 join)
        {
            var net = Singleton<NetManager>.instance;
            mean = Vector3.zero;
            var heading = Vector3.zero;
            foreach (ushort hook in hooks)
            {
                var n = net.m_nodes.m_buffer[hook];
                mean += n.m_position;
                if (n.CountSegments() == 1)
                {
                    for (int i = 0; i < 8; i++)
                    {
                        ushort sid = n.GetSegment(i);
                        if (sid == 0) continue;
                        var s = net.m_segments.m_buffer[sid];
                        heading -= s.m_startNode == hook ? s.m_startDirection : s.m_endDirection;
                    }
                }
            }
            mean /= hooks.Count;
            heading.y = 0;
            join = mean;
            if (heading.sqrMagnitude <= 0.1f) return false;
            // Native CanAddSegment rejects approaches less than ~41 degrees
            // apart. Keep the merge close enough for the two highway stubs.
            float approach = hooks.Count == 2
                ? Mathf.Clamp(VectorUtils.LengthXZ(net.m_nodes.m_buffer[hooks[0]].m_position
                    - net.m_nodes.m_buffer[hooks[1]].m_position) * 0.75f, 12, 96) : 96;
            join = mean + heading.normalized * approach;
            // Real ramp stubs can sit close together and face apart: push the
            // join out until each link is long enough for native placement.
            while (approach < 160f)
            {
                float nearest = float.MaxValue;
                foreach (ushort hook in hooks)
                    nearest = Mathf.Min(nearest, VectorUtils.LengthXZ(net.m_nodes.m_buffer[hook].m_position - join));
                if (nearest >= 40f) break;
                approach += 8f;
                join = mean + heading.normalized * approach;
            }
            return true;
        }

        static bool JoinLinksClear(List<ushort> hooks)
        {
            Vector3 mean, join;
            if (!JoinPoint(hooks, out mean, out join)) return true;
            var net = Singleton<NetManager>.instance;
            // The test-only links cannot see each other at the future junction.
            // Apply the same angular clearance as the grid's outgoing link.
            for (int i = 0; i < hooks.Count; i++)
                for (int j = i + 1; j < hooks.Count; j++)
                {
                    var a = net.m_nodes.m_buffer[hooks[i]].m_position - join; a.y = 0;
                    var b = net.m_nodes.m_buffer[hooks[j]].m_position - join; b.y = 0;
                    if (Vector3.Dot(a.normalized, b.normalized) > MaximumApproachDot)
                    {
                        if (result != null) result["last_hookup_join_rejection"] = "ramp approaches overlap at the proposed junction";
                        return false;
                    }
                }
            var road = Net("Basic Road");
            float elevation = Mathf.Max(0, mean.y - NetSegment.SampleTerrainHeight(road, join, false, 0));
            try
            {
                foreach (ushort hook in hooks)
                    Link(road, Vector3.zero, join, hook, 0, true, elevation, testOnly: true);
                return true;
            }
            catch (PlacementRejected e)
            {
                // Build uses these exact links without Connect's bridge recovery.
                // A rejected join is therefore not a constructible candidate.
                if (result != null) result["last_hookup_join_rejection"] = e.Message;
                return false;
            }
        }

        // A candidate grid must also be reachable: the hookup links from the
        // stubs and on to the nearest grid corner may not cross other networks.
        static bool HookupClear(List<ushort> hooks, Vector3 center)
        {
            var road = Net("Basic Road");
            var net = Singleton<NetManager>.instance;
            if (!JoinLinksClear(hooks)) return false;
            Vector3 mean, join;
            bool joined = JoinPoint(hooks, out mean, out join);
            var starts = new List<Vector3>();
            try
            {
                if (joined)
                {
                    starts.Add(join);
                }
                else
                    foreach (ushort hook in hooks) starts.Add(net.m_nodes.m_buffer[hook].m_position);
                foreach (var a in starts)
                {
                    var corner = Ground(center.x + (a.x < center.x ? -Half : Half), center.z + (a.z < center.z ? -Half : Half));
                    // The hook links don't exist yet, so the native test can't see
                    // the corner link doubling back over them: check the angle.
                    if (joined)
                    {
                        var toCorner = corner - join; toCorner.y = 0;
                        foreach (ushort hook in hooks)
                        {
                            var toHook = net.m_nodes.m_buffer[hook].m_position - join; toHook.y = 0;
                            if (Vector3.Dot(toCorner.normalized, toHook.normalized) > MaximumApproachDot) return false;
                        }
                    }
                    Link(road, Ground(a.x, a.z), corner, testOnly: true);
                }
            }
            catch (PlacementRejected e)
            {
                // Only the corner crossing goes through Connect's bridge retry.
                return (e.Errors & ~(ToolBase.ToolErrors.CannotBuildOnWater | ToolBase.ToolErrors.SlopeTooSteep)) == 0;
            }
            return true;
        }

        static Vector3 Site(List<ushort> hooks) { return Site(hooks, false).Value; }

        // strict: only a site whose hookup tests clear; null when there is none.
        static Vector3? Site(List<ushort> hooks, bool strict)
        {
            int tx, tz;
            Singleton<GameAreaManager>.instance.GetStartTile(out tx, out tz);
            var tile = new Vector3((tx - 2) * 1920, 0, (tz - 2) * 1920);
            var net = Singleton<NetManager>.instance;
            var tm = Singleton<TerrainManager>.instance;
            var candidates = new List<KeyValuePair<float, Vector3>>();
            for (float z = -672; z <= 672; z += 96)
                for (float x = -672; x <= 672; x += 96)
                {
                    var p = tile + new Vector3(x, 0, z);
                    float low = float.MaxValue, high = float.MinValue;
                    bool dry = true;
                    for (int j = -3; j <= 3 && dry; j++)
                        for (int i = -3; i <= 3; i++)
                        {
                            var q = Ground(p.x + i * 64, p.z + j * 64);
                            float ground, surface;
                            Vector3 velocity, normal;
                            if (tm.SampleWaterData(new Vector2(q.x, q.z), out ground, out surface, out velocity, out normal) && surface > q.y + 0.1f)
                            { dry = false; break; }
                            low = Mathf.Min(low, q.y);
                            high = Mathf.Max(high, q.y);
                        }
                    if (!dry || high - low > 32f)
                        continue;
                    // Keep the grid and its service strip clear of existing roads/rail.
                    bool clear = true;
                    for (int id = 1; id < net.m_nodes.m_buffer.Length; id++)
                    {
                        var n = net.m_nodes.m_buffer[id];
                        if ((n.m_flags & NetNode.Flags.Created) != 0
                            && Mathf.Abs(n.m_position.x - p.x) < Half + 64
                            && Mathf.Abs(n.m_position.z - p.z) < Half + 96)
                        { clear = false; break; }
                    }
                    if (!clear) continue;
                    float distance = 0;
                    foreach (ushort h in hooks)
                        distance += VectorUtils.LengthXZ(net.m_nodes.m_buffer[h].m_position - p);
                    float score = distance + (high - low) * 30f;
                    candidates.Add(new KeyValuePair<float, Vector3>(score, Ground(p.x, p.z)));
                }
            candidates.Sort((a, b) => a.Key.CompareTo(b.Key));
            foreach (var candidate in candidates)
            {
                var p = candidate.Value;
                try
                {
                    var road = Net("Basic Road");
                    for (int i = 0; i < 4; i++)
                        for (int j = 0; j < 3; j++)
                        {
                            var a = Ground(p.x - Half + j * Spacing, p.z - Half + i * Spacing);
                            Link(road, a, Ground(a.x + Spacing, a.z), testOnly: true);
                            a = Ground(p.x - Half + i * Spacing, p.z - Half + j * Spacing);
                            Link(road, a, Ground(a.x, a.z + Spacing), testOnly: true);
                        }
                    if (!HookupClear(hooks, p))
                    {
                        continue;
                    }
                    return p;
                }
                catch (PlacementRejected) { }
            }
            if (strict) return null;
            throw new Exception("no dry start-tile grid and hookup that pass native road placement checks");
        }

        static NetInfo Net(string name)
        {
            var p = PrefabCollection<NetInfo>.FindLoaded(name);
            if (p == null) throw new Exception("missing vanilla network prefab: " + name);
            return p;
        }

        static BuildingInfo BuildingPrefab(string name)
        {
            var p = PrefabCollection<BuildingInfo>.FindLoaded(name);
            if (p == null) throw new Exception("missing vanilla building prefab: " + name);
            return p;
        }

        static BuildingInfo WaterPrefab(bool intake)
        {
            BuildingInfo selected = null;
            int cheapest = int.MaxValue;
            for (uint i = 0; i < PrefabCollection<BuildingInfo>.LoadedCount(); i++)
            {
                var p = PrefabCollection<BuildingInfo>.GetLoaded(i);
                var ai = p == null ? null : p.m_buildingAI as WaterFacilityAI;
                if (ai == null || ai.m_waterStorage != 0 || ai.m_sewageStorage != 0) continue;
                // Distance alone cannot keep a shoreline intake upstream of its
                // drain, especially in a calm bay. Use vanilla groundwater when
                // the opening has no proven clean surface-water catchment.
                if (intake ? !ai.m_useGroundWater || ShoreMode(p) : !ShoreMode(p) || ai.m_useGroundWater) continue;
                if (intake ? ai.m_waterIntake <= 0 || ai.m_sewageOutlet != 0 : ai.m_sewageOutlet <= 0 || ai.m_waterIntake != 0) continue;
                if (!Singleton<UnlockManager>.instance.Unlocked(p.m_UnlockMilestone)) continue;
                int cost = ai.GetConstructionCost();
                if (cost < cheapest) { cheapest = cost; selected = p; }
            }
            if (selected == null) throw new Exception("no loaded " + (intake ? "groundwater supply" : "shoreline sewage drain"));
            return selected;
        }

        static bool ShoreMode(BuildingInfo info)
        {
            return info.m_placementMode == BuildingInfo.PlacementMode.Shoreline
                || info.m_placementMode == BuildingInfo.PlacementMode.ShorelineOrGround;
        }

        static NetTool.ControlPoint Point(NetInfo info, Vector3 p, ushort node = 0, float elevation = float.NaN)
        {
            if (float.IsNaN(elevation)) elevation = 0f;
            if (node != 0)
            {
                p = Singleton<NetManager>.instance.m_nodes.m_buffer[node].m_position;
                elevation = p.y - NetSegment.SampleTerrainHeight(info, p, false, 0);
                if (Mathf.Abs(elevation) < 1) elevation = 0;
            }
            else
                p.y = NetSegment.SampleTerrainHeight(info, p, false, elevation);
            return new NetTool.ControlPoint { m_position = p, m_node = node,
                m_elevation = elevation };
        }

        static ushort Link(NetInfo info, Vector3 a, Vector3 b, ushort from = 0, ushort to = 0, bool road = false,
            float endElevation = float.NaN, bool testOnly = false, List<ushort> endpoints = null)
        {
            var unlocks = Singleton<UnlockManager>.instance;
            unlocks.CheckMilestone(info.m_UnlockMilestone, false, false);
            if (!unlocks.Unlocked(info.m_UnlockMilestone)) throw new Exception("network is locked: " + info.name);
            var start = Point(info, a, from);
            var end = Point(info, b, to, endElevation);
            var dir = end.m_position - start.m_position;
            dir.y = 0;
            dir.Normalize();
            start.m_direction = dir;
            end.m_direction = dir;
            var mid = new NetTool.ControlPoint { m_position = (start.m_position + end.m_position) * 0.5f,
                m_direction = dir, m_elevation = start.m_elevation };
            var buffer = new FastList<NetTool.NodePosition>();
            ushort first, last, segment;
            int cost, production;
            var controller = Singleton<ToolManager>.instance.m_properties;
            ulong[] collidingSegments, collidingBuildings;
            controller.BeginColliding(out collidingSegments, out collidingBuildings);
            ToolBase.ToolErrors errors;
            try
            {
                errors = NetTool.CreateNode(info, start, mid, end, buffer, 1000, true, true, false, true, true, false, false, 0,
                    out first, out last, out segment, out cost, out production);
                if (errors != ToolBase.ToolErrors.None)
                    throw new PlacementRejected(info.name + " " + start.m_position + " -> " + end.m_position
                        + " (elevation " + start.m_elevation + " -> " + end.m_elevation + ")"
                        + CollisionDetail(collidingSegments, collidingBuildings), errors);
            }
            finally { controller.EndColliding(); }
            if (testOnly) return 0;
            errors = NetTool.CreateNode(info, start, mid, end, buffer, 1000, false, true, false, true, true, false, false, 0,
                out first, out last, out segment, out cost, out production);
            if (errors != ToolBase.ToolErrors.None || last == 0)
                throw new Exception(info.name + " construction failed: " + errors);
            if (road) roads.Add(segment);
            if (endpoints != null)
            {
                endpoints.Add(first);
                if (last != first) endpoints.Add(last);
            }
            return last;
        }

        static string CollisionDetail(ulong[] segments, ulong[] buildings)
        {
            var hits = new List<string>();
            var net = Singleton<NetManager>.instance;
            for (int i = 1; i < net.m_segments.m_buffer.Length && hits.Count < 8; i++)
                if ((segments[i >> 6] & (1UL << (i & 63))) != 0)
                {
                    var s = net.m_segments.m_buffer[i];
                    hits.Add("segment " + i + " " + (s.Info == null ? "?" : s.Info.name) + " " + s.m_flags);
                }
            var bm = Singleton<BuildingManager>.instance;
            for (int i = 1; i < bm.m_buildings.m_buffer.Length && hits.Count < 8; i++)
                if ((buildings[i >> 6] & (1UL << (i & 63))) != 0)
                {
                    var b = bm.m_buildings.m_buffer[i];
                    hits.Add("building " + i + " " + (b.Info == null ? "?" : b.Info.name));
                }
            return hits.Count == 0 ? "" : " [" + string.Join("; ", hits.ToArray()) + "]";
        }

        static void Connect(NetInfo road, ushort from, ushort to)
        {
            var net = Singleton<NetManager>.instance;
            var a = net.m_nodes.m_buffer[from].m_position;
            var b = net.m_nodes.m_buffer[to].m_position;
            try { Link(road, a, b, from, to, true); return; }
            catch (PlacementRejected e)
            {
                // Test mode has not constructed anything. A player would raise the
                // middle of this crossing; the native tool selects bridge/ramp prefabs.
                if ((e.Errors & (ToolBase.ToolErrors.CannotBuildOnWater | ToolBase.ToolErrors.SlopeTooSteep)) == 0) throw;
                result["crossing_ground_rejection"] = e.Message;
            }
            var mid = Ground((a.x + b.x) * 0.5f, (a.z + b.z) * 0.5f);
            float top = Mathf.Max(a.y, b.y);
            for (int i = 0; i <= 16; i++)
            {
                var p = Vector3.Lerp(a, b, i / 16f);
                top = Mathf.Max(top, Singleton<TerrainManager>.instance.SampleRawHeightSmoothWithWater(p, false, 0));
            }
            float elevation = Mathf.Max(12, top + 12 - NetSegment.SampleTerrainHeight(road, mid, false, 0));
            ushort bridge = Link(road, a, mid, from, 0, true, elevation);
            Link(road, mid, b, bridge, to, true);
        }

        static ushort Place(BuildingInfo info, Vector3 pos, float angle, float waterHeight = 0)
        {
            var unlocks = Singleton<UnlockManager>.instance;
            unlocks.CheckMilestone(info.m_UnlockMilestone, false, false);
            if (!unlocks.Unlocked(info.m_UnlockMilestone)) throw new Exception("building is locked: " + info.name);
            var connection = new Segment3();
            float low, high, height;
            Building.SampleBuildingHeight(pos, angle, info.m_cellWidth, info.m_cellLength, info, out low, out high, out height);
            bool shoreline = ShoreMode(info);
            var mode = shoreline ? BuildingInfo.PlacementMode.Shoreline : info.m_placementMode;
            float shoreHeight = pos.y;
            pos.y = shoreline ? Mathf.Max(pos.y, height) : height;
            int production, cost;
            var errors = info.m_buildingAI.CheckBuildPosition(0, ref pos, ref angle, waterHeight, 0, ref connection, out production, out cost);
            if (shoreline)
            {
                if (shoreHeight - waterHeight > 128) errors |= ToolBase.ToolErrors.HeightTooHigh;
                if (pos.y <= waterHeight) errors |= ToolBase.ToolErrors.ShoreNotFound;
                var facility = info.m_buildingAI as WaterFacilityAI;
                if (facility != null && facility.m_waterIntake > 0 && production == 0) errors |= ToolBase.ToolErrors.WaterNotFound;
            }
            var tool = Singleton<ToolManager>.instance.m_properties;
            ulong[] segments, bs;
            tool.BeginColliding(out segments, out bs);
            try
            {
                errors |= BuildingTool.CheckSpace(info, mode, 0, pos, Mathf.Min(low, waterHeight == 0 ? low : waterHeight),
                    pos.y + info.m_collisionHeight, angle, info.m_cellWidth, info.m_cellLength, true, segments, bs);
                if (!shoreline && high - low > info.m_maxHeightOffset) errors |= ToolBase.ToolErrors.SlopeTooSteep;
                if (Singleton<EconomyManager>.instance.PeekResource(EconomyManager.Resource.Construction, cost) != cost)
                    errors |= ToolBase.ToolErrors.NotEnoughMoney;
                if (errors != ToolBase.ToolErrors.None)
                    throw new PlacementRejected(info.name + " " + pos, errors);
                BuildingTool.CheckSpace(info, mode, 0, pos, low, pos.y + info.m_collisionHeight,
                    angle, info.m_cellWidth, info.m_cellLength, false, segments, bs);
            }
            finally { tool.EndColliding(); }
            var sm = Singleton<SimulationManager>.instance;
            ushort id;
            if (!Singleton<BuildingManager>.instance.CreateBuilding(out id, ref sm.m_randomizer, info, pos, angle, 0, sm.m_currentBuildIndex))
                throw new Exception("CreateBuilding refused " + info.name);
            sm.m_currentBuildIndex++;
            Singleton<EconomyManager>.instance.FetchResource(EconomyManager.Resource.Construction, cost, info.m_class);
            info.m_buildingAI.PlacementSucceeded();
            buildings.Add(id);
            return id;
        }

        static ushort Shore(BuildingInfo info, Vector3 near, Vector3 avoid, List<ushort> powerNodes)
        {
            var tm = Singleton<TerrainManager>.instance;
            var candidates = new List<Vector3>();
            int tx, tz;
            Singleton<GameAreaManager>.instance.GetStartTile(out tx, out tz);
            for (float z = -832; z <= 832; z += 32)
                for (float x = -832; x <= 832; x += 32)
                {
                    var p = Ground((tx - 2) * 1920 + x, (tz - 2) * 1920 + z);
                    if (VectorUtils.LengthXZ(p - avoid) >= 160)
                        candidates.Add(p);
                }
            candidates.Sort((a, b) => (a - near).sqrMagnitude.CompareTo((b - near).sqrMagnitude));
            string lastError = "no shoreline";
            foreach (var candidate in candidates)
            {
                Vector3 p, dir;
                float water;
                if (!tm.GetShorePos(candidate, 50f, out p, out dir, out water)
                    || !tm.GetShorePos(p, 50f, out p, out dir, out water)) continue;
                p += dir.normalized * info.m_placementOffset;
                if (!Inside(p, 64) || VectorUtils.LengthXZ(p - avoid) < 160) continue;
                float angle = Mathf.Atan2(dir.x, -dir.z);
                if (!PowerReachable(info, p, angle, powerNodes))
                { lastError = "no native power-line path to shoreline at " + p; continue; }
                try { return Place(info, p, angle, water); }
                catch (PlacementRejected e)
                {
                    if ((e.Errors & ToolBase.ToolErrors.NotEnoughMoney) != 0) throw;
                    lastError = e.Message;
                }
            }
            throw new Exception("cannot place " + info.name + ": " + lastError);
        }

        static ushort Groundwater(BuildingInfo info, ushort plant, List<ushort> powerNodes)
        {
            int tx, tz;
            Singleton<GameAreaManager>.instance.GetStartTile(out tx, out tz);
            var tm = Singleton<TerrainManager>.instance;
            var plantPosition = Singleton<BuildingManager>.instance.m_buildings.m_buffer[plant].m_position;
            var candidates = new List<KeyValuePair<float, Vector3>>();
            // Keep the source 400 m beyond the entire planned industrial strip,
            // not merely away from today's empty ground or a single building.
            // The coal plant is another separate ground-pollution source.
            for (float z = -832; z <= 832; z += 32)
                for (float x = -832; x <= 832; x += 32)
                {
                    var p = Ground((tx - 2) * 1920 + x, (tz - 2) * 1920 + z);
                    float dx = Mathf.Max(0, Mathf.Abs(p.x - center.x) - Half - 32);
                    float dz = Mathf.Max(center.z + 80 - p.z, Mathf.Max(0, p.z - center.z - Half - 32));
                    if (Mathf.Sqrt(dx * dx + dz * dz) < 400
                        || VectorUtils.LengthXZ(p - plantPosition) < 400) continue;
                    float ground, surface;
                    Vector3 velocity, normal;
                    if (tm.SampleWaterData(new Vector2(p.x, p.z), out ground, out surface, out velocity, out normal)
                        && surface > p.y + 0.1f) continue;
                    candidates.Add(new KeyValuePair<float, Vector3>(VectorUtils.LengthXZ(p - center), p));
                }
            candidates.Sort((a, b) => a.Key.CompareTo(b.Key));
            string lastError = "no dry groundwater site separated from starter pollution";
            foreach (var candidate in candidates)
            {
                var p = candidate.Value;
                if (!PowerReachable(info, p, 0, powerNodes)) continue;
                try
                {
                    ushort source = Place(info, p, 0);
                    result["water_supply"] = Host.Obj("mode", "groundwater", "source", source,
                        "pollution_setback_m", 400, "planned_industrial_strip", true,
                        "surface_upstream_relationship", "not assumed");
                    return source;
                }
                catch (PlacementRejected e)
                {
                    if ((e.Errors & ToolBase.ToolErrors.NotEnoughMoney) != 0) throw;
                    lastError = e.Message;
                }
            }
            throw new Exception("cannot place " + info.name + ": " + lastError);
        }

        static ushort Roadside(BuildingInfo info)
        {
            string lastError = "no legal roadside site";
            foreach (var away in new Vector3[] { Vector3.forward, Vector3.right, Vector3.left, Vector3.back })
                foreach (float along in new float[] { 0, -96, 96 })
                {
                    var tangent = new Vector3(away.z, 0, -away.x);
                    var p = center + away * (Half + 8 + info.m_cellLength * 4) + tangent * along;
                    p = Ground(p.x, p.z);
                    // CalculateSidewalkPosition puts the road at local +Z for angle 0.
                    float angle = Mathf.Atan2(away.x, -away.z);
                    try { return Place(info, p, angle); }
                    catch (PlacementRejected e)
                    {
                        if ((e.Errors & ToolBase.ToolErrors.NotEnoughMoney) != 0) throw;
                        lastError = e.Message;
                    }
                }
            throw new Exception("cannot place " + info.name + ": " + lastError);
        }

        static void Zone()
        {
            var zm = Singleton<ZoneManager>.instance;
            int residential = 0, commercial = 0, industrial = 0;
            for (int i = 1; i < zm.m_blocks.m_buffer.Length; i++)
            {
                var b = zm.m_blocks.m_buffer[i];
                if ((b.m_flags & 1) == 0) continue;
                var right = new Vector3(Mathf.Cos(b.m_angle), 0, Mathf.Sin(b.m_angle)) * 8;
                var forward = new Vector3(right.z, 0, -right.x);
                bool changed = false;
                for (int z = 0; z < b.RowCount; z++)
                    for (int x = 0; x < 4; x++)
                    {
                        var p = b.m_position + (x - 3.5f) * right + (z - 3.5f) * forward;
                        if (Mathf.Abs(p.x - center.x) > Half + 32 || Mathf.Abs(p.z - center.z) > Half + 32) continue;
                        var zone = p.z > center.z + 80 ? ItemClass.Zone.Industrial
                            : p.x > center.x + 80 ? ItemClass.Zone.CommercialLow : ItemClass.Zone.ResidentialLow;
                        if (b.GetZone(x, z) != ItemClass.Zone.Unzoned) continue;
                        changed |= b.SetZone(x, z, zone);
                        if (zone == ItemClass.Zone.ResidentialLow) residential++;
                        else if (zone == ItemClass.Zone.CommercialLow) commercial++;
                        else industrial++;
                    }
                zm.m_blocks.m_buffer[i] = b;
                if (changed) zm.m_blocks.m_buffer[i].RefreshZoning((ushort)i);
            }
            result["zoned_cells"] = Host.Obj("residential", residential, "commercial", commercial, "industrial", industrial);
            if (residential == 0 || commercial == 0 || industrial == 0)
                throw new Exception("the road grid produced no zone cells for one of R/C/I");
        }

        static List<ushort> NetworkNodes(NetInfo info, List<ushort> nodes)
        {
            var net = Singleton<NetManager>.instance;
            var origins = new List<ushort>();
            var pending = new Queue<ushort>(nodes);
            var seen = new HashSet<ushort>();
            while (pending.Count != 0)
            {
                ushort id = pending.Dequeue();
                if (!seen.Add(id)) continue;
                var n = net.m_nodes.m_buffer[id];
                if ((n.m_flags & (NetNode.Flags.Created | NetNode.Flags.Deleted)) != NetNode.Flags.Created) continue;
                origins.Add(id);
                for (int i = 0; i < 8; i++)
                {
                    ushort sid = n.GetSegment(i);
                    if (sid == 0) continue;
                    var s = net.m_segments.m_buffer[sid];
                    if (s.Info == null || s.Info.m_class.m_service != info.m_class.m_service) continue;
                    pending.Enqueue(s.m_startNode == id ? s.m_endNode : s.m_startNode);
                }
            }
            return origins;
        }

        static List<Vector3> PowerEnds(BuildingInfo info, Vector3 pos, float angle)
        {
            var ends = new List<Vector3>();
            const float cell = ElectricityManager.ELECTRICITYGRID_CELL_SIZE;
            float radius = info.m_buildingAI.ElectricityGridRadius();
            float reach = Mathf.Sqrt(info.m_cellWidth * info.m_cellWidth + info.m_cellLength * info.m_cellLength) * 4 + radius;
            int minX = Mathf.Clamp((int)((pos.x - reach) / cell + 128), 0, 255);
            int maxX = Mathf.Clamp((int)((pos.x + reach) / cell + 128), 0, 255);
            int minZ = Mathf.Clamp((int)((pos.z - reach) / cell + 128), 0, 255);
            int maxZ = Mathf.Clamp((int)((pos.z + reach) / cell + 128), 0, 255);
            var axis = new Vector3(Mathf.Cos(angle), 0, Mathf.Sin(angle));
            var across = new Vector3(axis.z, 0, -axis.x);
            for (int z = minZ; z <= maxZ; z++)
                for (int x = minX; x <= maxX; x++)
                {
                    var p = Ground((x + 0.5f - 128) * cell, (z + 0.5f - 128) * cell);
                    var delta = p - pos;
                    float dx = Mathf.Max(0, Mathf.Abs(Vector3.Dot(axis, delta)) - info.m_cellWidth * 4);
                    float dz = Mathf.Max(0, Mathf.Abs(Vector3.Dot(across, delta)) - info.m_cellLength * 4);
                    int conductivity = Mathf.Min(255, Mathf.RoundToInt(((radius - Mathf.Sqrt(dx * dx + dz * dz))
                        * (2 / (cell * 4)) + 0.25f) * 255));
                    // ElectricityManager rejects fringe cells below this limit unless
                    // they have conductive neighbours on both axes. Connect to the core.
                    if (conductivity >= ElectricityManager.CONDUCTIVITY_LIMIT) ends.Add(p);
                }
            return ends;
        }

        static bool PowerReachable(BuildingInfo info, Vector3 pos, float angle, List<ushort> nodes)
        {
            var ai = info.m_buildingAI as WaterFacilityAI;
            if (ai != null && ai.m_electricityConsumption == 0) return true;
            var wire = Net("Power Line");
            var ends = PowerEnds(info, pos, angle);
            foreach (ushort id in NetworkNodes(wire, nodes))
            {
                var origin = Singleton<NetManager>.instance.m_nodes.m_buffer[id].m_position;
                foreach (var end in ends)
                    try { Link(wire, origin, end, id, testOnly: true); return true; }
                    catch (PlacementRejected e)
                    {
                        if ((e.Errors & ToolBase.ToolErrors.NotEnoughMoney) != 0) throw;
                    }
            }
            return false;
        }

        static void Supply(NetInfo info, ushort building, List<ushort> nodes)
        {
            var net = Singleton<NetManager>.instance;
            var facility = Singleton<BuildingManager>.instance.m_buildings.m_buffer[building];
            var target = facility.m_position;
            bool electricity = info.m_class.m_service == ItemClass.Service.Electricity;
            var waterAI = facility.Info.m_buildingAI as WaterFacilityAI;
            if (electricity && waterAI != null && waterAI.m_electricityConsumption == 0) return;
            ushort destination = electricity ? (ushort)0 : facility.m_netNode;
            if (!electricity)
            {
                if (destination == 0) throw new Exception("water facility has no native pipe connection node: " + building);
                target = net.m_nodes.m_buffer[destination].m_position;
            }
            var ends = new List<Vector3> { target };
            if (electricity)
                ends = PowerEnds(facility.Info, target, facility.m_angle);
            var origins = NetworkNodes(info, nodes);
            origins.Sort((a, b) => (net.m_nodes.m_buffer[a].m_position - target).sqrMagnitude
                .CompareTo((net.m_nodes.m_buffer[b].m_position - target).sqrMagnitude));
            string lastError = "no usable network endpoint";
            var rejected = new List<object>();
            result["utility_last_rejections"] = rejected;
            foreach (ushort origin in origins)
            {
                if (electricity)
                {
                    var source = net.m_nodes.m_buffer[origin].m_position;
                    ends.Sort((a, b) => (a - source).sqrMagnitude.CompareTo((b - source).sqrMagnitude));
                }
                foreach (var end in ends)
                {
                    try
                    {
                        ushort node = Link(info, Vector3.zero, end, origin, destination);
                        nodes.Add(node);
                        return;
                    }
                    catch (PlacementRejected e)
                    {
                        if ((e.Errors & ToolBase.ToolErrors.NotEnoughMoney) != 0) throw;
                        lastError = e.Message;
                        if (rejected.Count < 8) rejected.Add(lastError);
                    }
                }
            }
            // A straight wire can collide with the plant or the road grid. Test a
            // dogleg before constructing either leg, keeping normal tool checks.
            foreach (ushort origin in origins)
                foreach (var end in ends)
                {
                    var start = net.m_nodes.m_buffer[origin].m_position;
                    var bends = new Vector3[] {
                        Ground(start.x, end.z), Ground(end.x, start.z),
                        Ground(center.x - Half - 64, center.z + Half + 128),
                        Ground(center.x + Half + 64, center.z + Half + 128),
                        Ground(center.x - Half - 64, center.z - Half - 128),
                        Ground(center.x + Half + 64, center.z - Half - 128)
                    };
                    foreach (var bend in bends)
                    {
                        var a = bend - start; a.y = 0; a.Normalize();
                        var b = end - bend; b.y = 0; b.Normalize();
                        if (Vector3.Dot(-a, b) > 0.75f) continue;
                        try
                        {
                            Link(info, start, bend, origin, testOnly: true);
                            Link(info, bend, end, to: destination, testOnly: true);
                        }
                        catch (PlacementRejected e)
                        {
                            if ((e.Errors & ToolBase.ToolErrors.NotEnoughMoney) != 0) throw;
                            lastError = e.Message;
                            continue;
                        }
                        ushort middle = Link(info, start, bend, origin);
                        ushort node = Link(info, bend, end, middle, destination);
                        nodes.Add(node);
                        return;
                    }
                }
            throw new Exception("cannot connect " + info.name + " to building " + building + ": " + lastError);
        }

        static Dictionary<string, object> Start(Dictionary<string, object> q)
        {
            var sm = Singleton<SimulationManager>.instance;
            string instance = sm.m_metaData.m_gameInstanceIdentifier;
            if (city == instance && state != "idle")
                throw new Exception("test-city already attempted in this city; use a fresh New Game");
            if (!sm.SimulationPaused || Singleton<DistrictManager>.instance.m_districts.m_buffer[0].m_populationData.m_finalCount != 0)
                throw new Exception("test-city needs a paused, empty New Game");
            city = instance;
            // UnlockManager still grants normal milestones and rewards, but its
            // modal presentation would pause a headless growth soak.
            Singleton<UnlockManager>.instance.RegisterUnlockingPanel(null);
            state = "building";
            error = null;
            roads.Clear(); buildings.Clear();
            result = Host.Obj("name", "test-city", "money_before", Singleton<EconomyManager>.instance.InternalCashAmount);
            sm.AddAction(() =>
            {
                try { Build(); state = "done"; }
                catch (Exception e) { error = e.ToString(); state = "failed"; }
            });
            return Host.Obj("state", state);
        }

        static void Build()
        {
            var net = Singleton<NetManager>.instance;
            var bm = Singleton<BuildingManager>.instance;
            int tx, tz;
            Singleton<GameAreaManager>.instance.GetStartTile(out tx, out tz);
            result["start_tile"] = new object[] { tx, tz };
            result["land"] = Land(tx, tz);
            result["hookup_candidates"] = HookupInfo();
            List<ushort> hooks = null;
            foreach (var pair in HookupPairs())
            {
                var site = Site(pair, true);
                if (site != null) { hooks = pair; center = site.Value; break; }
            }
            if (hooks == null)
            {
                hooks = Hookups();
                center = Site(hooks);
            }
            result["center"] = XYZ(center);
            result["hookup_nodes"] = hooks;
            var road = Net("Basic Road");
            var pipe = Net("Water Pipe");
            var power = Net("Power Line");
            var grid = new ushort[4, 4];
            // Rows first, then join their existing junction nodes with columns.
            for (int z = 0; z < 4; z++)
                for (int x = 0; x < 3; x++)
                {
                    var a = Ground(center.x - Half + x * Spacing, center.z - Half + z * Spacing);
                    var b = Ground(a.x + Spacing, a.z);
                    grid[x + 1, z] = Link(road, a, b, grid[x, z], 0, true);
                    if (x == 0)
                    {
                        ushort segment = roads[roads.Count - 1];
                        grid[0, z] = net.m_segments.m_buffer[segment].m_startNode;
                    }
                }
            for (int x = 0; x < 4; x++)
                for (int z = 0; z < 3; z++)
                    Link(road, Vector3.zero, Vector3.zero, grid[x, z], grid[x, z + 1], true);
            ushort junction = 0;
            Vector3 mean, join;
            if (JoinPoint(hooks, out mean, out join))
            {
                float elevation = Mathf.Max(0, mean.y - NetSegment.SampleTerrainHeight(road, join, false, 0));
                junction = Link(road, Vector3.zero, join, hooks[0], 0, true, elevation);
                for (int i = 1; i < hooks.Count; i++)
                    Link(road, Vector3.zero, Vector3.zero, hooks[i], junction, true);
            }
            foreach (ushort hook in junction != 0 ? new List<ushort> { junction } : hooks)
            {
                var p = net.m_nodes.m_buffer[hook].m_position;
                Connect(road, hook, grid[p.x < center.x ? 0 : 3, p.z < center.z ? 0 : 3]);
            }

            // A normal roadside coal plant; no forced completion or resource buffers.
            var plantInfo = BuildingPrefab("Coal Power Plant");
            ushort plant = Roadside(plantInfo);
            Vector3 powerHub = Ground(center.x - Half - 48, center.z + Half + 48);
            var powerEnds = new List<ushort>();
            Link(power, powerHub, Ground(center.x - Half - 48, center.z - Half - 24), endpoints: powerEnds);
            Supply(power, plant, powerEnds);
            ushort pump = Groundwater(WaterPrefab(true), plant, powerEnds);
            Supply(power, pump, powerEnds);
            ushort drain = Shore(WaterPrefab(false), center, bm.m_buildings.m_buffer[pump].m_position, powerEnds);
            Supply(power, drain, powerEnds);
            // One connected pipe tree covers the grid and attaches directly to
            // each facility's native pipe connection node.
            var hub = Ground(center.x, center.z);
            ushort pipeHub = Link(pipe, Ground(center.x - Half, center.z), hub);
            Link(pipe, hub, Ground(center.x + Half, center.z), pipeHub);
            var pipeEnds = new List<ushort>();
            foreach (float dz in new float[] { -96, 96 })
            {
                var p = Ground(center.x, center.z + dz);
                ushort spine = Link(pipe, hub, p, pipeHub);
                pipeEnds.Add(Link(pipe, p, Ground(center.x - Half - 32, p.z), spine));
                pipeEnds.Add(Link(pipe, p, Ground(center.x + Half + 32, p.z), spine));
            }
            Supply(pipe, pump, pipeEnds);
            Supply(pipe, drain, pipeEnds);
            Zone();
            result["money_after"] = Singleton<EconomyManager>.instance.InternalCashAmount;
            result["road_segments"] = roads.ToArray();
            result["buildings"] = buildings.ToArray();
        }

        static Dictionary<string, object> Status(Dictionary<string, object> q)
        {
            if (state == "building")
                return Host.Obj("state", state);
            var live = new List<object>();
            foreach (ushort id in buildings)
            {
                var b = Singleton<BuildingManager>.instance.m_buildings.m_buffer[id];
                bool electricity;
                Singleton<ElectricityManager>.instance.CheckElectricity(b.m_position, out electricity);
                var water = b.Info.m_buildingAI as WaterFacilityAI;
                string role = water == null ? "power" : water.m_waterIntake > 0 ? "water" : "sewage";
                live.Add(Host.Obj("id", id, "name", b.Info == null ? null : b.Info.name, "position", XYZ(b.m_position),
                    "role", role, "net_node", b.m_netNode,
                    "connected_segments", b.m_netNode == 0 ? 0 : Singleton<NetManager>.instance.m_nodes.m_buffer[b.m_netNode].CountSegments(),
                    "flags", b.m_flags.ToString(), "problems", b.m_problems.ToString(),
                    "electricity", b.m_electricityBuffer, "water", b.m_waterBuffer, "sewage", b.m_sewageBuffer,
                    "electricity_grid_powered", electricity,
                    "requires_electricity", b.Info.m_buildingAI.GetElectricityConsumption() > 0,
                    "width", b.Width, "length", b.Length, "electricity_rate", b.Info.m_buildingAI.GetElectricityRate(id, ref b)));
            }
            var doc = Host.Obj("state", state, "error", error, "result", result, "utilities", live);
            if (state == "done")
            {
                doc["traffic"] = Traffic();
                var grown = Host.Obj("Residential", 0, "Commercial", 0, "Industrial", 0);
                var problems = new Dictionary<string, object>();
                var bm = Singleton<BuildingManager>.instance;
                for (int i = 1; i < bm.m_buildings.m_buffer.Length; i++)
                {
                    var b = bm.m_buildings.m_buffer[i];
                    if ((b.m_flags & (Building.Flags.Created | Building.Flags.Deleted)) != Building.Flags.Created || b.Info == null
                        || Mathf.Abs(b.m_position.x - center.x) > Half + 40 || Mathf.Abs(b.m_position.z - center.z) > Half + 40) continue;
                    string service = b.Info.m_class.m_service.ToString();
                    if (!grown.ContainsKey(service)) continue;
                    grown[service] = (int)grown[service] + 1;
                    if (b.m_problems.IsNotNone)
                    {
                        string key = b.m_problems.ToString();
                        problems[key] = problems.ContainsKey(key) ? (int)problems[key] + 1 : 1;
                    }
                }
                doc["growables"] = grown;
                doc["growable_problems"] = problems;
            }
            if (Json.Bool(q, "inspect", false))
            {
                int x, z;
                Singleton<GameAreaManager>.instance.GetStartTile(out x, out z);
                doc["start_tile"] = new object[] { x, z };
                doc["hookups"] = HookupInfo();
                var water = new List<object>();
                for (uint i = 0; i < PrefabCollection<BuildingInfo>.LoadedCount(); i++)
                {
                    var p = PrefabCollection<BuildingInfo>.GetLoaded(i);
                    var ai = p == null ? null : p.m_buildingAI as WaterFacilityAI;
                    if (ai == null) continue;
                    water.Add(Host.Obj("name", p.name, "mode", p.m_placementMode.ToString(), "intake", ai.m_waterIntake,
                        "outlet", ai.m_waterOutlet, "sewage", ai.m_sewageOutlet, "storage", ai.m_waterStorage,
                        "sewage_storage", ai.m_sewageStorage, "ground_water", ai.m_useGroundWater, "cost", ai.GetConstructionCost(),
                        "width", p.m_cellWidth, "length", p.m_cellLength, "electricity_consumption", ai.m_electricityConsumption,
                        "unlocked", Singleton<UnlockManager>.instance.Unlocked(p.m_UnlockMilestone)));
                }
                doc["water_prefabs"] = water;
            }
            return doc;
        }

        static Dictionary<string, object> Land(int tx, int tz)
        {
            var tm = Singleton<TerrainManager>.instance;
            int samples = 0, dryFlat = 0;
            for (float z = -944; z < 960; z += 32)
                for (float x = -944; x < 960; x += 32)
                {
                    var p = Ground((tx - 2) * 1920 + x, (tz - 2) * 1920 + z);
                    float ground, surface;
                    Vector3 velocity, normal;
                    bool wet = tm.SampleWaterData(new Vector2(p.x, p.z), out ground, out surface, out velocity, out normal)
                        && surface > p.y + 0.1f;
                    float dx = Mathf.Abs(Ground(p.x + 8, p.z).y - Ground(p.x - 8, p.z).y) / 16;
                    float dz = Mathf.Abs(Ground(p.x, p.z + 8).y - Ground(p.x, p.z - 8).y) / 16;
                    samples++;
                    if (!wet && Mathf.Max(dx, dz) <= 0.15f) dryFlat++;
                }
            return Host.Obj("samples", samples, "dry_flat_samples", dryFlat, "sample_spacing_m", 32,
                "max_axis_slope", 0.15f, "dry_flat_km2", dryFlat * 32f * 32f / 1000000f,
                "dry_flat_fraction", (float)dryFlat / samples);
        }

        static Dictionary<string, object> Traffic()
        {
            int total = 0, moving = 0;
            var vm = Singleton<VehicleManager>.instance;
            var pm = Singleton<PathManager>.instance;
            var scenarioRoads = new HashSet<ushort>(roads);
            for (int i = 1; i < vm.m_vehicles.m_buffer.Length; i++)
            {
                var v = vm.m_vehicles.m_buffer[i];
                var flags = Vehicle.Flags.Created | Vehicle.Flags.Spawned;
                if ((v.m_flags & flags) != flags || v.Info == null
                    || (v.Info.m_vehicleType & VehicleInfo.VehicleType.Car) == 0) continue;
                PathUnit.Position position;
                lock (pm.m_bufferLock)
                {
                    if (v.m_path == 0 || !pm.m_pathUnits.m_buffer[v.m_path].GetPosition(v.m_pathPositionIndex >> 1, out position))
                        continue;
                }
                if (!scenarioRoads.Contains(position.m_segment)) continue;
                total++;
                if (v.GetLastFrameData().m_velocity.sqrMagnitude > 0.01f) moving++;
            }
            return Host.Obj("scope", "scenario road segments", "segments", scenarioRoads.Count, "vehicles", total, "moving", moving,
                "stationary", total - moving, "moving_velocity_squared_min", 0.01f);
        }

        static PathUnit.Position Lane(ushort segment, int choice)
        {
            var info = Singleton<NetManager>.instance.m_segments.m_buffer[segment].Info;
            int seen = 0;
            for (int i = 0; i < info.m_lanes.Length; i++)
                if ((info.m_lanes[i].m_laneType & NetInfo.LaneType.Vehicle) != 0
                    && (info.m_lanes[i].m_vehicleType & VehicleInfo.VehicleType.Car) != 0)
                {
                    if (seen++ == choice)
                        return new PathUnit.Position { m_segment = segment, m_lane = (byte)i, m_offset = 128 };
                }
            return default(PathUnit.Position);
        }

        static bool EdgeNode(ushort id)
        {
            var n = Singleton<NetManager>.instance.m_nodes.m_buffer[id];
            return (n.m_flags & NetNode.Flags.Outside) != 0
                && Mathf.Max(Mathf.Abs(n.m_position.x), Mathf.Abs(n.m_position.z)) >= 8500;
        }

        static PathUnit.Position EdgeLane(ushort segment, bool outbound, int choice)
        {
            var s = Singleton<NetManager>.instance.m_segments.m_buffer[segment];
            bool atStart = EdgeNode(s.m_startNode);
            var want = atStart == outbound ? NetInfo.Direction.Backward : NetInfo.Direction.Forward;
            if ((s.m_flags & NetSegment.Flags.Invert) != 0)
                want = want == NetInfo.Direction.Forward ? NetInfo.Direction.Backward : NetInfo.Direction.Forward;
            int seen = 0;
            for (int i = 0; i < s.Info.m_lanes.Length; i++)
            {
                var lane = s.Info.m_lanes[i];
                if ((lane.m_laneType & NetInfo.LaneType.Vehicle) == 0 || (lane.m_vehicleType & VehicleInfo.VehicleType.Car) == 0
                    || (lane.m_finalDirection & want) == 0) continue;
                if (seen++ == choice)
                    return new PathUnit.Position { m_segment = segment, m_lane = (byte)i, m_offset = atStart ? (byte)0 : (byte)255 };
            }
            return default(PathUnit.Position);
        }

        static Dictionary<string, object> Paths(Dictionary<string, object> q)
        {
            var pm = Singleton<PathManager>.instance;
            if (Json.Bool(q, "start", false))
            {
                if (paths.Count != 0) throw new Exception("poll pending scenario paths first");
                if (state != "done") throw new Exception("build test-city first");
                pathResults.Clear(); pathDirections.Clear(); pathEdges.Clear();
                var net = Singleton<NetManager>.instance;
                var random = new Randomizer(893u);
                var fromA = Lane(roads[0], 0);
                var fromB = Lane(roads[0], 1);
                for (int id = 1; id < net.m_segments.m_buffer.Length; id++)
                {
                    var s = net.m_segments.m_buffer[id];
                    if ((s.m_flags & NetSegment.Flags.Created) == 0 || s.Info == null || !(s.Info.m_netAI is RoadBaseAI)) continue;
                    if (!EdgeNode(s.m_startNode) && !EdgeNode(s.m_endNode)) continue;
                    for (int direction = 0; direction < 2; direction++)
                    {
                        var toA = EdgeLane((ushort)id, direction == 0, 0);
                        var toB = EdgeLane((ushort)id, direction == 0, 1);
                        if (toA.m_segment == 0) continue;
                        if (paths.Count >= 32) throw new Exception("more than 32 scenario edge path requests");
                        uint path;
                        bool created = direction == 0
                            ? pm.CreatePath(out path, ref random, Singleton<SimulationManager>.instance.m_currentBuildIndex, fromA, fromB, toA, toB,
                                NetInfo.LaneType.Vehicle, VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.PassengerCar, 100000f)
                            : pm.CreatePath(out path, ref random, Singleton<SimulationManager>.instance.m_currentBuildIndex, toA, toB, fromA, fromB,
                                NetInfo.LaneType.Vehicle, VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.PassengerCar, 100000f);
                        if (!created) throw new Exception("native CreatePath refused the scenario probe");
                        paths.Add(path);
                        pathDirections.Add(direction == 0 ? "outbound" : "inbound");
                        pathEdges.Add(toA);
                    }
                }
            }
            for (int i = paths.Count - 1; i >= 0; i--)
            {
                uint id = paths[i];
                var positions = new List<object>();
                byte flags;
                float length;
                lock (pm.m_bufferLock)
                {
                    var first = pm.m_pathUnits.m_buffer[id];
                    flags = first.m_pathFindFlags;
                    length = first.m_length;
                    if ((flags & 12) == 0) continue;
                    uint part = id;
                    var seen = new HashSet<uint>();
                    while ((flags & 4) != 0 && part != 0 && seen.Add(part))
                    {
                        var unit = pm.m_pathUnits.m_buffer[part];
                        for (int p = 0; p < unit.m_positionCount; p++)
                        {
                            PathUnit.Position pos;
                            if (unit.GetPosition(p, out pos)) positions.Add(new object[] { pos.m_segment, pos.m_lane, pos.m_offset });
                        }
                        part = unit.m_nextPathUnit;
                    }
                }
                pathResults.Add(Host.Obj("direction", pathDirections[i], "success", (flags & 4) != 0,
                    "length", length, "positions", positions, "released", true, "grid_segment", roads[0],
                    "edge_segment", pathEdges[i].m_segment, "edge_offset", pathEdges[i].m_offset));
                pm.ReleasePath(id);
                paths.RemoveAt(i); pathDirections.RemoveAt(i); pathEdges.RemoveAt(i);
            }
            bool inbound = false, outbound = false;
            foreach (var p in pathResults)
                if ((bool)p["success"])
                { if ((string)p["direction"] == "outbound") outbound = true; else inbound = true; }
            return Host.Obj("complete", paths.Count == 0, "inbound", inbound, "outbound", outbound, "paths", pathResults);
        }
    }
}
