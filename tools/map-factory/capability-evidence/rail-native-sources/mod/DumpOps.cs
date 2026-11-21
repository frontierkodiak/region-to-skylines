using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using ColossalFramework;
using UnityEngine;

namespace Cs1Harness
{
    // Whole-city dumps for checking an offline save reader against the game (PL-984):
    // the live buffers as columns keyed by buffer id, and the loaded prefab catalog.
    // Both write a JSON file and return its path; neither changes the city.
    public static class DumpOps
    {
        public static void Register()
        {
            Host.Register("dump_city", Needs.City, "write every node, segment, building, zone block and tree to {path} (absolute .json)", DumpCity);
            Host.Register("dump_prefabs", Needs.Level, "write the loaded building, net and tree prefab catalog to {path} (absolute .json)", DumpPrefabs);
        }

        static string OutPath(Dictionary<string, object> q)
        {
            string path = Json.Str(q, "path", "");
            if (string.IsNullOrEmpty(path) || !Path.IsPathRooted(path))
                throw new Exception("needs an absolute {path}");
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            return path;
        }

        // Saved name of a simulation prefab index (kept even when the prefab is missing),
        // and whether the game bound it to a loaded prefab.
        static string NetName(ushort i) { return i < PrefabCollection<NetInfo>.PrefabCount() ? PrefabCollection<NetInfo>.PrefabName(i) : null; }
        static string BuildingName(ushort i) { return i < PrefabCollection<BuildingInfo>.PrefabCount() ? PrefabCollection<BuildingInfo>.PrefabName(i) : null; }
        static string TreeName(ushort i) { return i < PrefabCollection<TreeInfo>.PrefabCount() ? PrefabCollection<TreeInfo>.PrefabName(i) : null; }

        static string U64(ulong v) { return v.ToString(CultureInfo.InvariantCulture); }

        static Dictionary<string, object> DumpCity(Dictionary<string, object> q)
        {
            string path = OutPath(q);
            var sm = Singleton<SimulationManager>.instance;
            var nm = Singleton<NetManager>.instance;
            var bm = Singleton<BuildingManager>.instance;
            var zm = Singleton<ZoneManager>.instance;
            var tm = Singleton<TreeManager>.instance;

            var nodes = Columns("id", "flags", "x", "y", "z", "prefab", "bound");
            var nb = nm.m_nodes.m_buffer;
            for (int i = 1; i < nb.Length; i++)
            {
                if (nb[i].m_flags == NetNode.Flags.None)
                    continue;
                var p = nb[i].m_position;
                Add(nodes, i, (uint)nb[i].m_flags, p.x, p.y, p.z, NetName(nb[i].m_infoIndex), nb[i].Info != null);
            }

            var segments = Columns("id", "flags", "start_node", "end_node", "prefab", "bound");
            var sb = nm.m_segments.m_buffer;
            for (int i = 1; i < sb.Length; i++)
            {
                if (sb[i].m_flags == NetSegment.Flags.None)
                    continue;
                Add(segments, i, (uint)sb[i].m_flags, (int)sb[i].m_startNode, (int)sb[i].m_endNode, NetName(sb[i].m_infoIndex), sb[i].Info != null);
            }

            var buildings = Columns("id", "flags", "prefab", "bound", "x", "y", "z", "angle", "level", "width", "length");
            var bb = bm.m_buildings.m_buffer;
            for (int i = 1; i < bb.Length; i++)
            {
                if (bb[i].m_flags == Building.Flags.None)
                    continue;
                var p = bb[i].m_position;
                Add(buildings, i, (uint)bb[i].m_flags, BuildingName(bb[i].m_infoIndex), bb[i].Info != null,
                    p.x, p.y, p.z, bb[i].m_angle, (int)bb[i].m_level, (int)bb[i].m_width, (int)bb[i].m_length);
            }

            var blocks = Columns("id", "flags", "x", "y", "z", "angle", "valid", "zone1", "zone2");
            var zb = zm.m_blocks.m_buffer;
            for (int i = 1; i < zb.Length; i++)
            {
                if (zb[i].m_flags == 0)
                    continue;
                var p = zb[i].m_position;
                Add(blocks, i, zb[i].m_flags, p.x, p.y, p.z, zb[i].m_angle, U64(zb[i].m_valid), U64(zb[i].m_zone1), U64(zb[i].m_zone2));
            }

            // Raw position shorts are what the save stores; Position applies the game's scale.
            var trees = Columns("id", "flags", "prefab", "pos_x", "pos_z");
            var tb = tm.m_trees.m_buffer;
            for (int i = 1; i < tb.Length; i++)
            {
                if (tb[i].m_flags == 0)
                    continue;
                Add(trees, i, (int)tb[i].m_flags, TreeName(tb[i].m_infoIndex), (int)tb[i].m_posX, (int)tb[i].m_posZ);
            }

            var district = Singleton<DistrictManager>.instance.m_districts.m_buffer[0];
            var economy = Singleton<EconomyManager>.instance;
            var dump = Host.Obj(
                "frame", sm.m_currentFrameIndex,
                "paused", sm.SimulationPaused,
                "population", district.m_populationData.m_finalCount,
                "cash", economy.LastCashAmount,
                "internal_cash", economy.InternalCashAmount,
                "counts", Host.Obj(
                    "nodes", (int)nm.m_nodeCount, "segments", (int)nm.m_segmentCount, "lanes", (int)nm.m_laneCount,
                    "buildings", (int)bm.m_buildingCount, "zone_blocks", (int)zm.m_blockCount, "trees", (int)tm.m_treeCount),
                "nodes", nodes.ToObj(),
                "segments", segments.ToObj(),
                "buildings", buildings.ToObj(),
                "zone_blocks", blocks.ToObj(),
                "trees", trees.ToObj()
            );
            File.WriteAllText(path, Json.Write(dump));
            return Host.Obj(
                "path", path,
                "frame", sm.m_currentFrameIndex,
                "paused", sm.SimulationPaused,
                "nodes", Count(nodes), "segments", Count(segments), "buildings", Count(buildings),
                "zone_blocks", Count(blocks), "trees", Count(trees)
            );
        }

        static Dictionary<string, object> DumpPrefabs(Dictionary<string, object> q)
        {
            string path = OutPath(q);
            var buildings = new List<object>();
            for (uint i = 0; i < PrefabCollection<BuildingInfo>.LoadedCount(); i++)
            {
                var b = PrefabCollection<BuildingInfo>.GetLoaded(i);
                if (b == null)
                    continue;
                var d = Class(b.name, b.m_class);
                d["ai"] = b.m_buildingAI == null ? null : b.m_buildingAI.GetType().Name;
                d["cell_width"] = b.m_cellWidth;
                d["cell_length"] = b.m_cellLength;
                d["placement"] = b.m_placementStyle.ToString();
                d["data_index"] = b.m_prefabDataIndex;
                buildings.Add(d);
            }
            var nets = new List<object>();
            for (uint i = 0; i < PrefabCollection<NetInfo>.LoadedCount(); i++)
            {
                var n = PrefabCollection<NetInfo>.GetLoaded(i);
                if (n == null)
                    continue;
                var d = Class(n.name, n.m_class);
                d["ai"] = n.m_netAI == null ? null : n.m_netAI.GetType().Name;
                d["half_width"] = n.m_halfWidth;
                d["vehicle_lanes"] = n.m_hasForwardVehicleLanes || n.m_hasBackwardVehicleLanes;
                d["forward_vehicle_lanes"] = n.m_hasForwardVehicleLanes;
                d["backward_vehicle_lanes"] = n.m_hasBackwardVehicleLanes;
                d["vehicle_types"] = n.m_vehicleTypes.ToString();
                d["lane_types"] = n.m_laneTypes.ToString();
                d["lanes"] = n.m_lanes == null ? 0 : n.m_lanes.Length;
                d["data_index"] = n.m_prefabDataIndex;
                nets.Add(d);
            }
            var trees = new List<object>();
            for (uint i = 0; i < PrefabCollection<TreeInfo>.LoadedCount(); i++)
            {
                var t = PrefabCollection<TreeInfo>.GetLoaded(i);
                if (t == null)
                    continue;
                var d = Class(t.name, t.m_class);
                d["data_index"] = t.m_prefabDataIndex;
                trees.Add(d);
            }
            File.WriteAllText(path, Json.Write(Host.Obj("buildings", buildings, "nets", nets, "trees", trees)));
            return Host.Obj("path", path, "buildings", buildings.Count, "nets", nets.Count, "trees", trees.Count);
        }

        static Dictionary<string, object> Class(string name, ItemClass c)
        {
            return Host.Obj(
                "name", name,
                "class", c == null ? null : c.name,
                "service", c == null ? null : c.m_service.ToString(),
                "sub_service", c == null ? null : c.m_subService.ToString(),
                "level", c == null ? null : c.m_level.ToString()
            );
        }

        // Columns in a fixed order, so Add's values line up whatever order a
        // Dictionary enumerates in.
        sealed class Table
        {
            public readonly string[] Names;
            public readonly List<object>[] Cols;

            public Table(string[] names)
            {
                Names = names;
                Cols = new List<object>[names.Length];
                for (int i = 0; i < names.Length; i++)
                    Cols[i] = new List<object>();
            }

            public Dictionary<string, object> ToObj()
            {
                var d = new Dictionary<string, object>();
                for (int i = 0; i < Names.Length; i++)
                    d[Names[i]] = Cols[i];
                return d;
            }
        }

        static Table Columns(params string[] names)
        {
            return new Table(names);
        }

        static void Add(Table t, params object[] values)
        {
            if (values.Length != t.Names.Length)
                throw new Exception("column count mismatch");
            for (int i = 0; i < values.Length; i++)
                t.Cols[i].Add(values[i]);
        }

        static int Count(Table t)
        {
            return t.Cols[0].Count;
        }
    }
}
