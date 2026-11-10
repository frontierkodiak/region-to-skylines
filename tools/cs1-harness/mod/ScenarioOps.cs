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
            Host.Register("scenario_status", Needs.City, "construction result and live utility/building state (inspect:true lists hookup nodes)", Status);
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

        static List<ushort> Hookups()
        {
            var net = Singleton<NetManager>.instance;
            var ends = new List<ushort>();
            var nodes = new List<ushort>();
            for (int i = 1; i < net.m_nodes.m_buffer.Length; i++)
            {
                var n = net.m_nodes.m_buffer[i];
                if ((n.m_flags & (NetNode.Flags.Created | NetNode.Flags.Deleted | NetNode.Flags.Outside)) != NetNode.Flags.Created
                    || n.Info == null || !(n.Info.m_netAI is RoadBaseAI) || !Inside(n.m_position, 48))
                    continue;
                nodes.Add((ushort)i);
                if (n.CountSegments() == 1)
                    ends.Add((ushort)i);
            }
            var chosen = ends.Count != 0 ? ends : nodes;
            chosen.Sort((a, b) => net.m_nodes.m_buffer[a].m_position.sqrMagnitude.CompareTo(net.m_nodes.m_buffer[b].m_position.sqrMagnitude));
            if (chosen.Count == 0)
                throw new Exception("no road hookup node in the start tile; map needs an accessible highway connection");
            // A vanilla interchange has two one-way ends. A through-road map can
            // instead be joined at existing nodes, without replacing its network.
            if (chosen.Count > 2)
                chosen.RemoveRange(2, chosen.Count - 2);
            return chosen;
        }

        static Vector3 Site(List<ushort> hooks)
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
                    return p;
                }
                catch (PlacementRejected) { }
            }
            throw new Exception("no dry start-tile site whose grid passes native road placement checks");
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

        static NetTool.ControlPoint Point(NetInfo info, Vector3 p, ushort node = 0, float elevation = float.NaN)
        {
            if (float.IsNaN(elevation)) elevation = info.m_netAI.IsUnderground() ? -12f : 0f;
            if (node != 0)
            {
                p = Singleton<NetManager>.instance.m_nodes.m_buffer[node].m_position;
                elevation = Singleton<NetManager>.instance.m_nodes.m_buffer[node].m_elevation;
                if (info.m_netAI.IsUnderground()) elevation = -elevation;
            }
            else
                p.y = NetSegment.SampleTerrainHeight(info, p, false, elevation);
            return new NetTool.ControlPoint { m_position = p, m_node = node,
                m_elevation = elevation };
        }

        static ushort Link(NetInfo info, Vector3 a, Vector3 b, ushort from = 0, ushort to = 0, bool road = false,
            float endElevation = float.NaN, bool testOnly = false, List<ushort> endpoints = null)
        {
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
            var errors = NetTool.CreateNode(info, start, mid, end, buffer, 1000, true, true, false, true, true, false, false, 0,
                out first, out last, out segment, out cost, out production);
            if (errors != ToolBase.ToolErrors.None)
                throw new PlacementRejected(info.name + " " + a + " -> " + b, errors);
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
            float elevation = Mathf.Max(12, top + 12 - mid.y);
            ushort bridge = Link(road, a, mid, from, 0, true, elevation);
            Link(road, mid, b, bridge, to, true);
        }

        static ushort Place(BuildingInfo info, Vector3 pos, float angle, float waterHeight = 0)
        {
            var connection = new Segment3();
            float low, high, height;
            Building.SampleBuildingHeight(pos, angle, info.m_cellWidth, info.m_cellLength, info, out low, out high, out height);
            bool shoreline = info.m_placementMode == BuildingInfo.PlacementMode.Shoreline;
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
                errors |= BuildingTool.CheckSpace(info, info.m_placementMode, 0, pos, Mathf.Min(low, waterHeight == 0 ? low : waterHeight),
                    pos.y + info.m_collisionHeight, angle, info.m_cellWidth, info.m_cellLength, true, segments, bs);
                if (!shoreline && high - low > info.m_maxHeightOffset) errors |= ToolBase.ToolErrors.SlopeTooSteep;
                if (Singleton<EconomyManager>.instance.PeekResource(EconomyManager.Resource.Construction, cost) != cost)
                    errors |= ToolBase.ToolErrors.NotEnoughMoney;
                if (errors != ToolBase.ToolErrors.None)
                    throw new PlacementRejected(info.name + " " + pos, errors);
                BuildingTool.CheckSpace(info, info.m_placementMode, 0, pos, low, pos.y + info.m_collisionHeight,
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

        static ushort Shore(BuildingInfo info, Vector3 near, Vector3 avoid)
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
                try { return Place(info, p, angle, water); }
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

        static ushort Supply(NetInfo info, ushort building, List<ushort> nodes, float standOff)
        {
            var net = Singleton<NetManager>.instance;
            var target = Singleton<BuildingManager>.instance.m_buildings.m_buffer[building].m_position;
            var origins = new List<ushort>(nodes);
            origins.Sort((a, b) => (net.m_nodes.m_buffer[a].m_position - target).sqrMagnitude
                .CompareTo((net.m_nodes.m_buffer[b].m_position - target).sqrMagnitude));
            string lastError = "no usable network endpoint";
            foreach (ushort origin in origins)
                for (int i = 0; i < (standOff == 0 ? 1 : 8); i++)
                {
                    var end = target + new Vector3(Mathf.Cos(i * Mathf.PI / 4), 0, Mathf.Sin(i * Mathf.PI / 4)) * standOff;
                    try
                    {
                        ushort node = Link(info, Vector3.zero, end, origin);
                        nodes.Add(node);
                        return node;
                    }
                    catch (PlacementRejected e)
                    {
                        if ((e.Errors & ToolBase.ToolErrors.NotEnoughMoney) != 0) throw;
                        lastError = e.Message;
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
            var hooks = Hookups();
            center = Site(hooks);
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
            var mean = Vector3.zero;
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
            if (heading.sqrMagnitude > 0.1f)
            {
                // Native CanAddSegment rejects approaches less than ~41 degrees
                // apart. Keep the merge close enough for the two highway stubs.
                float approach = hooks.Count == 2
                    ? Mathf.Clamp(VectorUtils.LengthXZ(net.m_nodes.m_buffer[hooks[0]].m_position
                        - net.m_nodes.m_buffer[hooks[1]].m_position) * 0.75f, 12, 96) : 96;
                var join = mean + heading.normalized * approach;
                junction = Link(road, Vector3.zero, join, hooks[0], 0, true);
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
            var distant = new Vector3(100000, 0, 100000);
            ushort pump = Shore(BuildingPrefab("Water Pumping Station"), center, distant);
            ushort drain = Shore(BuildingPrefab("Water Drain Pipe"), center, bm.m_buildings.m_buffer[pump].m_position);
            // One connected pipe tree covers the whole grid. Native pipes couple to
            // facilities by proximity, as when drawn with the pipe tool.
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
            Supply(pipe, pump, pipeEnds, 0);
            Supply(pipe, drain, pipeEnds, 0);
            // Keep pylons outside the road/zone footprint; the two trunks supply
            // both facilities and early growables before they form a power grid.
            Vector3 powerHub = Ground(center.x - Half - 48, center.z + Half + 48);
            var powerEnds = new List<ushort>();
            Link(power, powerHub, Ground(center.x - Half - 48, center.z - Half - 24), endpoints: powerEnds);
            Supply(power, plant, powerEnds, 40);
            Supply(power, pump, powerEnds, 40);
            Supply(power, drain, powerEnds, 40);
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
                live.Add(Host.Obj("id", id, "name", b.Info == null ? null : b.Info.name, "position", XYZ(b.m_position),
                    "flags", b.m_flags.ToString(), "problems", b.m_problems.ToString(),
                    "electricity", b.m_electricityBuffer, "water", b.m_waterBuffer, "sewage", b.m_sewageBuffer));
            }
            var doc = Host.Obj("state", state, "error", error, "result", result, "utilities", live);
            if (state == "done")
            {
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
                var hooks = new List<object>();
                foreach (ushort h in Hookups())
                {
                    var n = Singleton<NetManager>.instance.m_nodes.m_buffer[h];
                    hooks.Add(Host.Obj("node", h, "position", XYZ(n.m_position), "prefab", n.Info.name, "segments", n.CountSegments()));
                }
                doc["hookups"] = hooks;
            }
            return doc;
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
