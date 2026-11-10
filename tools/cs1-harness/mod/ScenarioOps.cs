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
        static Vector3 center;

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
            float best = float.MaxValue;
            Vector3 selected = Vector3.zero;
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
                    if (score < best) { best = score; selected = Ground(p.x, p.z); }
                }
            if (best == float.MaxValue)
                throw new Exception("no dry 384 m site with <=32 m relief in the start tile");
            return selected;
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

        static NetTool.ControlPoint Point(NetInfo info, Vector3 p, ushort node = 0)
        {
            if (node != 0)
                p = Singleton<NetManager>.instance.m_nodes.m_buffer[node].m_position;
            else
                p.y = NetSegment.SampleTerrainHeight(info, p, false, info.m_netAI.IsUnderground() ? -12f : 0f);
            return new NetTool.ControlPoint { m_position = p, m_node = node,
                m_elevation = info.m_netAI.IsUnderground() ? -12f : 0f };
        }

        static ushort Link(NetInfo info, Vector3 a, Vector3 b, ushort from = 0, ushort to = 0, bool road = false)
        {
            var start = Point(info, a, from);
            var end = Point(info, b, to);
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
                throw new Exception(info.name + " " + a + " -> " + b + ": " + errors);
            errors = NetTool.CreateNode(info, start, mid, end, buffer, 1000, false, true, false, true, true, false, false, 0,
                out first, out last, out segment, out cost, out production);
            if (errors != ToolBase.ToolErrors.None || last == 0)
                throw new Exception(info.name + " construction failed: " + errors);
            if (road) roads.Add(segment);
            return last;
        }

        static ushort Place(BuildingInfo info, Vector3 pos, float angle, float waterHeight = 0)
        {
            var connection = new Segment3();
            float low, high, height;
            Building.SampleBuildingHeight(pos, angle, info.m_cellWidth, info.m_cellLength, info, out low, out high, out height);
            pos.y = Mathf.Max(pos.y, height);
            int production, cost;
            var errors = info.m_buildingAI.CheckBuildPosition(0, ref pos, ref angle, waterHeight, 0, ref connection, out production, out cost);
            var tool = Singleton<ToolManager>.instance.m_properties;
            ulong[] segments, bs;
            tool.BeginColliding(out segments, out bs);
            try
            {
                errors |= BuildingTool.CheckSpace(info, info.m_placementMode, 0, pos, Mathf.Min(low, waterHeight == 0 ? low : waterHeight),
                    pos.y + info.m_collisionHeight, angle, info.m_cellWidth, info.m_cellLength, true, segments, bs);
                if (high - low > info.m_maxHeightOffset) errors |= ToolBase.ToolErrors.SlopeTooSteep;
                if (Singleton<EconomyManager>.instance.PeekResource(EconomyManager.Resource.Construction, cost) != cost)
                    errors |= ToolBase.ToolErrors.NotEnoughMoney;
                if (errors != ToolBase.ToolErrors.None)
                    throw new Exception(info.name + " " + pos + ": " + errors);
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
            for (float z = -832; z <= 832; z += 32)
                for (float x = -832; x <= 832; x += 32)
                {
                    int tx, tz;
                    Singleton<GameAreaManager>.instance.GetStartTile(out tx, out tz);
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
                catch (Exception e) { lastError = e.Message; }
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

        static Dictionary<string, object> Start(Dictionary<string, object> q)
        {
            var sm = Singleton<SimulationManager>.instance;
            string instance = sm.m_metaData.m_gameInstanceIdentifier;
            if (city == instance && state != "idle")
                throw new Exception("test-city already attempted in this city; use a fresh New Game");
            if (!sm.SimulationPaused || Singleton<DistrictManager>.instance.m_districts.m_buffer[0].m_populationData.m_finalCount != 0)
                throw new Exception("test-city needs a paused, empty New Game");
            city = instance;
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
            foreach (ushort hook in hooks)
            {
                var p = net.m_nodes.m_buffer[hook].m_position;
                int gx = p.x < center.x ? 0 : 3;
                int gz = p.z < center.z ? 0 : 3;
                Link(road, p, net.m_nodes.m_buffer[grid[gx, gz]].m_position, hook, grid[gx, gz], true);
            }

            // A normal roadside coal plant; no forced completion or resource buffers.
            var plantInfo = BuildingPrefab("Coal Power Plant");
            Vector3 plantPos = Ground(center.x, center.z + Half + 8 + plantInfo.m_cellLength * 4);
            ushort plant = Place(plantInfo, plantPos, 0);
            var distant = new Vector3(100000, 0, 100000);
            ushort pump = Shore(BuildingPrefab("Water Pumping Station"), center, distant);
            ushort drain = Shore(BuildingPrefab("Water Drain Pipe"), center, bm.m_buildings.m_buffer[pump].m_position);
            // One connected pipe tree covers the whole grid. Native pipes couple to
            // facilities by proximity, as when drawn with the pipe tool.
            var hub = Ground(center.x, center.z);
            ushort pipeHub = Link(pipe, Ground(center.x - Half, center.z), hub);
            Link(pipe, hub, Ground(center.x + Half, center.z), pipeHub);
            Link(pipe, hub, Ground(center.x, center.z - Half), pipeHub);
            Link(pipe, hub, Ground(center.x, center.z + Half), pipeHub);
            Link(pipe, hub, bm.m_buildings.m_buffer[pump].m_position, pipeHub);
            Link(pipe, hub, bm.m_buildings.m_buffer[drain].m_position, pipeHub);
            // Keep pylons outside the road/zone footprint; the two trunks supply
            // both facilities and early growables before they form a power grid.
            Vector3 powerHub = Ground(center.x - Half - 48, center.z + Half + 48);
            ushort powerNode = Link(power, plantPos + new Vector3(-48, 0, 0), powerHub);
            Link(power, powerHub, Ground(center.x - Half - 48, center.z - Half - 24), powerNode);
            Link(power, powerHub, bm.m_buildings.m_buffer[pump].m_position + new Vector3(40, 0, 0), powerNode);
            Link(power, powerHub, bm.m_buildings.m_buffer[drain].m_position + new Vector3(40, 0, 0), powerNode);
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

        static Dictionary<string, object> Paths(Dictionary<string, object> q)
        {
            var pm = Singleton<PathManager>.instance;
            if (Json.Bool(q, "start", false))
            {
                if (paths.Count != 0) throw new Exception("poll pending scenario paths first");
                if (state != "done") throw new Exception("build test-city first");
                pathResults.Clear(); pathDirections.Clear();
                var net = Singleton<NetManager>.instance;
                var random = new Randomizer(893u);
                var fromA = Lane(roads[0], 0);
                var fromB = Lane(roads[0], 1);
                for (int id = 1; id < net.m_segments.m_buffer.Length; id++)
                {
                    var s = net.m_segments.m_buffer[id];
                    if ((s.m_flags & NetSegment.Flags.Created) == 0 || s.Info == null || !(s.Info.m_netAI is RoadBaseAI)) continue;
                    if (((net.m_nodes.m_buffer[s.m_startNode].m_flags | net.m_nodes.m_buffer[s.m_endNode].m_flags) & NetNode.Flags.Outside) == 0) continue;
                    var toA = Lane((ushort)id, 0);
                    var toB = Lane((ushort)id, 1);
                    if (toA.m_segment == 0) continue;
                    if (paths.Count >= 32) throw new Exception("more than 16 road edge segments; scenario path probe limit exceeded");
                    for (int direction = 0; direction < 2; direction++)
                    {
                        uint path;
                        bool created = direction == 0
                            ? pm.CreatePath(out path, ref random, Singleton<SimulationManager>.instance.m_currentBuildIndex, fromA, fromB, toA, toB,
                                NetInfo.LaneType.Vehicle, VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.PassengerCar, 100000f)
                            : pm.CreatePath(out path, ref random, Singleton<SimulationManager>.instance.m_currentBuildIndex, toA, toB, fromA, fromB,
                                NetInfo.LaneType.Vehicle, VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.PassengerCar, 100000f);
                        if (!created) throw new Exception("native CreatePath refused the scenario probe");
                        paths.Add(path);
                        pathDirections.Add(direction == 0 ? "outbound" : "inbound");
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
                    "length", length, "positions", positions, "released", true));
                pm.ReleasePath(id);
                paths.RemoveAt(i); pathDirections.RemoveAt(i);
            }
            bool inbound = false, outbound = false;
            foreach (var p in pathResults)
                if ((bool)p["success"])
                { if ((string)p["direction"] == "outbound") outbound = true; else inbound = true; }
            return Host.Obj("complete", paths.Count == 0, "inbound", inbound, "outbound", outbound, "paths", pathResults);
        }
    }
}
