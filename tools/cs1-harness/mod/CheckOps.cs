using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using ColossalFramework;
using ColossalFramework.Math;
using ColossalFramework.Packaging;
using ColossalFramework.UI;
using UnityEngine;

namespace Cs1Harness
{
    // In-game asset checks (PL-880): find a custom building the game loaded, place it, light it
    // for day or night, and save and reload the city to see that it survives.
    public static class CheckOps
    {
        public static void Register()
        {
            Host.Register("custom_assets", Needs.Any, "custom asset packages, and (once a level has loaded them) their buildings with mesh, LOD and texture details: {contains}", CustomAssets);
            Host.Register("place_building", Needs.City, "place a building, completed, at {position:[x,z], angle (deg), name}", Place);
            Host.Register("building", Needs.City, "one building's state: {id}", q => BuildingState((ushort)Json.Num(q, "id", 0)));
            Host.Register("time_of_day", Needs.City, "day/night on (this session only) and the clock at {hour}", TimeOfDay);
            Host.Register("save_game", Needs.City, "job: save the city as {name} (the game's save panel routine)", SaveGame);
            Host.Register("load_game", Needs.Level, "job: load a saved city: {name}", LoadGame);
        }

        static Dictionary<string, object> CustomAssets(Dictionary<string, object> q)
        {
            string contains = Json.Str(q, "contains", "");
            var list = new List<object>();
            uint n = (uint)PrefabCollection<BuildingInfo>.LoadedCount();
            for (uint i = 0; i < n; i++)
            {
                var b = PrefabCollection<BuildingInfo>.GetLoaded(i);
                if (b == null || !b.name.Contains("."))
                    continue; // built-in prefabs have no package prefix
                if (contains != "" && b.name.IndexOf(contains, StringComparison.OrdinalIgnoreCase) < 0)
                    continue;
                var d = EditorOps.Describe(b);
                d["lod_distance"] = new object[] { b.m_minLodDistance, b.m_maxLodDistance };
                list.Add(d);
            }
            var metas = new List<object>();
            foreach (var a in PackageManager.FilterAssets(UserAssetType.CustomAssetMetaData))
            {
                if (a == null || !a.isMainAsset)
                    continue;
                if (contains != "" && a.fullName.IndexOf(contains, StringComparison.OrdinalIgnoreCase) < 0)
                    continue;
                CustomAssetMetaData m = null;
                try
                {
                    m = a.Instantiate<CustomAssetMetaData>();
                }
                catch { }
                var mods = new List<object>();
                if (m != null && m.mods != null)
                    foreach (var mod in m.mods)
                        mods.Add(mod.modName);
                metas.Add(Host.Obj(
                    "asset", a.fullName,
                    "path", a.package.packagePath,
                    "enabled", a.isEnabled,
                    "type", m == null ? null : m.type.ToString(),
                    "template", m == null ? null : m.templateName,
                    "embedded_mods", mods
                ));
            }
            return Host.Obj("buildings", list, "packages", metas);
        }

        static BuildingInfo FindBuilding(string name)
        {
            var b = PrefabCollection<BuildingInfo>.FindLoaded(name);
            if (b != null)
                return b;
            BuildingInfo match = null;
            uint n = (uint)PrefabCollection<BuildingInfo>.LoadedCount();
            for (uint i = 0; i < n; i++)
            {
                var x = PrefabCollection<BuildingInfo>.GetLoaded(i);
                if (x != null && x.name.IndexOf(name, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    if (match != null)
                        throw new Exception("'" + name + "' matches more than one building: " + match.name + ", " + x.name);
                    match = x;
                }
            }
            if (match == null)
                throw new Exception("no loaded building matches '" + name + "'; `custom_assets` lists them");
            return match;
        }

        // A growable created by hand starts as a construction site and, unzoned and without a
        // road, would be abandoned once the simulation runs. The check places it completed and
        // keeps the simulation paused, so what renders is the asset itself.
        static Dictionary<string, object> Place(Dictionary<string, object> q)
        {
            var info = FindBuilding(Json.Str(q, "name", ""));
            var p = (List<object>)q["position"];
            var pos = new Vector3(Convert.ToSingle(p[0]), 0, Convert.ToSingle(p[1]));
            pos.y = Singleton<TerrainManager>.instance.SampleRawHeightSmooth(pos);
            float angle = (float)Json.Num(q, "angle", 0) * Mathf.Deg2Rad;
            Singleton<SimulationManager>.instance.SimulationPaused = true;
            var job = Jobs.Start("place_building", j => PlaceSteps(j, info, pos, angle));
            return Host.Obj("job", job.Id, "name", info.name);
        }

        // Simulation actions run on the simulation thread, also while paused; the job waits
        // for this one frame by frame.
        static IEnumerator PlaceSteps(Job job, BuildingInfo info, Vector3 pos, float angle)
        {
            job.Note("creating " + info.name);
            ushort id = 0;
            var sm = Singleton<SimulationManager>.instance;
            var action = sm.AddAction(() =>
            {
                var bm = Singleton<BuildingManager>.instance;
                ushort created;
                if (!bm.CreateBuilding(out created, ref sm.m_randomizer, info, pos, angle, info.m_cellLength, sm.m_currentBuildIndex))
                    return;
                sm.m_currentBuildIndex++;
                var b = bm.m_buildings.m_buffer[created];
                b.m_flags = (b.m_flags | Building.Flags.Completed) & ~Building.Flags.Upgrading;
                b.m_frame0.m_constructState = 255;
                b.m_frame1.m_constructState = 255;
                b.m_frame2.m_constructState = 255;
                b.m_frame3.m_constructState = 255;
                bm.m_buildings.m_buffer[created] = b;
                bm.UpdateBuildingRenderer(created, true);
                id = created;
            });
            yield return Jobs.Until(() => action.completedOrFailed, 30, "the simulation thread to create the building");
            if (id == 0)
                throw new Exception("the game refused to create the building (no free slot, or the action failed)");
            foreach (var kv in BuildingState(id))
                job.Result[kv.Key] = kv.Value;
            job.Result["info"] = EditorOps.Describe(info);
            job.Result["lod_distance"] = new object[] { info.m_minLodDistance, info.m_maxLodDistance };
        }

        static Dictionary<string, object> BuildingState(ushort id)
        {
            var b = Singleton<BuildingManager>.instance.m_buildings.m_buffer[id];
            if ((b.m_flags & Building.Flags.Created) == 0)
                return Host.Obj("id", id, "exists", false);
            var info = b.Info;
            return Host.Obj(
                "id", id,
                "exists", true,
                "name", info == null ? null : info.name,
                "position", new object[] { b.m_position.x, b.m_position.y, b.m_position.z },
                "angle_deg", b.m_angle * Mathf.Rad2Deg,
                "cells", new object[] { b.Width, b.Length },
                "flags", b.m_flags.ToString(),
                "construct_state", b.m_frame0.m_constructState
            );
        }

        static Dictionary<string, object> TimeOfDay(Dictionary<string, object> q)
        {
            var sm = Singleton<SimulationManager>.instance;
            float hour = (float)Json.Num(q, "hour", 12);
            // The field is loaded from the player's setting at startup; changing the field (not
            // the setting) lasts only for this game process.
            sm.m_enableDayNight = true;
            uint frames = SimulationManager.DAYTIME_FRAMES;
            uint target = (uint)Mathf.RoundToInt(hour * SimulationManager.DAYTIME_HOUR_TO_FRAME) & (frames - 1);
            sm.m_dayTimeOffsetFrames = (target - sm.m_referenceFrameIndex) & (frames - 1);
            return Host.Obj("hour", hour, "day_night", sm.m_enableDayNight, "offset_frames", sm.m_dayTimeOffsetFrames);
        }

        static string SaveFilePath(string name)
        {
            return (string)Reflect.CallStatic(typeof(SavePanel), "GetSavePathName", name, false);
        }

        static Dictionary<string, object> SaveGame(Dictionary<string, object> q)
        {
            string name = Json.Str(q, "name", "");
            if (name == "")
                throw new Exception("save_game needs {name}");
            string path = SaveFilePath(name);
            if (File.Exists(path))
                throw new Exception(path + " exists; pick another name");
            var panel = UIView.library.Get<SavePanel>("SavePanel");
            if (panel == null)
                throw new Exception("no SavePanel in this scene");
            var job = Jobs.Start("save_game", j => SaveSteps(j, panel, name, path));
            return Host.Obj("job", job.Id, "path", path);
        }

        static IEnumerator SaveSteps(Job job, SavePanel panel, string name, string path)
        {
            job.Result["path"] = path;
            job.Note("saving " + name);
            if (!panel.SaveGame(name))
                throw new Exception("the save panel refused (already saving, or loading)");
            yield return Jobs.Until(() => !SavePanel.isSaving && File.Exists(path), 300, "the save to finish");
            job.Result["bytes"] = new FileInfo(path).Length;
        }

        static Dictionary<string, object> LoadGame(Dictionary<string, object> q)
        {
            string name = Json.Str(q, "name", "");
            string path = Path.GetFullPath(SaveFilePath(name));
            if (!File.Exists(path))
                throw new Exception("no saved game at " + path);
            Package.Asset found = null;
            for (int pass = 0; pass < 2 && found == null; pass++)
            {
                if (pass == 1)
                    PackageManager.Add(new Package(name, path)); // not yet picked up by the folder watcher
                foreach (var a in PackageManager.FilterAssets(UserAssetType.SaveGameMetaData))
                    if (a != null && a.package.packagePath != null && Path.GetFullPath(a.package.packagePath) == path)
                        found = a;
            }
            if (found == null)
                throw new Exception("the game has no save-game asset in " + path);
            var meta = found.Instantiate<SaveGameMetaData>();
            var sim = new SimulationMetaData { m_CityName = meta.cityName, m_updateMode = SimulationManager.UpdateMode.LoadGame };
            if (Singleton<LoadingManager>.instance.LoadLevel(meta.assetRef, "Game", "InGame", sim) == null)
                throw new Exception("LoadingManager refused the save");
            return Host.Obj("loading", path, "city", meta.cityName);
        }
    }
}
