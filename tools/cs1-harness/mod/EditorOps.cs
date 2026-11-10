using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using ColossalFramework;
using ColossalFramework.IO;
using ColossalFramework.Packaging;
using ColossalFramework.PlatformServices;
using ColossalFramework.UI;
using UnityEngine;

namespace Cs1Harness
{
    // Asset Editor mode (PL-880): open the editor, import a model onto a template, set the lot,
    // save a .crp. It drives the game's own wizard and save panel, the way CSUR RoadImporter
    // does for roads: named components and their handlers, never screen coordinates. The game
    // version these member names were read from is 1.21.1-f9.
    public static class EditorOps
    {
        public static void Register()
        {
            Host.Register("themes", Needs.Any, "built-in Asset Editor themes (environments)", q => Themes());
            Host.Register("asset_editor", Needs.MainMenu, "open the Asset Editor on a new asset: {theme}", OpenEditor);
            Host.Register("templates", Needs.AssetEditor, "building templates: {service, sub_service, level, width, length, limit}", Templates);
            Host.Register(
                "asset_build",
                Needs.AssetEditor,
                "job: import <name>.fbx (+ <name>_lod.fbx and maps) from Addons/Import onto a building template, "
                    + "set the lot, save a .crp: {name, template, cells:[w,l], scale, expect_size:[x,y,z], "
                    + "asset_name, save_name, description, overwrite, keep_import}",
                Build
            );
            Host.Register("job", Needs.Any, "the current or last job: state, step, log, result", q => Jobs.Status());
        }

        static Dictionary<string, object> Themes()
        {
            var themes = new List<object>();
            foreach (var a in PackageManager.FilterAssets(UserAssetType.SystemMapMetaData))
            {
                if (a == null || !a.isEnabled)
                    continue;
                var m = a.Instantiate<SystemMapMetaData>();
                themes.Add(Host.Obj("environment", m.environment, "asset", a.fullName));
            }
            return Host.Obj("themes", themes);
        }

        // Mirrors NewAssetBuiltinThemePanel.OnCreate.
        static Dictionary<string, object> OpenEditor(Dictionary<string, object> q)
        {
            string want = Json.Str(q, "theme", "Sunny");
            Package.Asset theme = null;
            var seen = new List<string>();
            foreach (var a in PackageManager.FilterAssets(UserAssetType.SystemMapMetaData))
            {
                if (a == null || !a.isEnabled)
                    continue;
                var m = a.Instantiate<SystemMapMetaData>();
                seen.Add(m.environment);
                if (string.Equals(m.environment, want, StringComparison.OrdinalIgnoreCase))
                    theme = a;
            }
            if (theme == null)
                throw new Exception("no built-in theme '" + want + "'; have " + string.Join(", ", seen.ToArray()));
            var sim = new SimulationMetaData
            {
                m_gameInstanceIdentifier = Guid.NewGuid().ToString(),
                m_WorkshopPublishedFileId = PublishedFileId.invalid,
                m_updateMode = SimulationManager.UpdateMode.NewAsset,
                m_invertTraffic = SimulationMetaData.MetaBool.False,
            };
            Singleton<LoadingManager>.instance.LoadLevel(theme, "AssetEditor", "InAssetEditor", sim, true);
            return Host.Obj("loading", "AssetEditor", "theme", want);
        }

        static Dictionary<string, object> Templates(Dictionary<string, object> q)
        {
            string service = Json.Str(q, "service", "Residential");
            string sub = Json.Str(q, "sub_service", "");
            int level = (int)Json.Num(q, "level", 0);
            int width = (int)Json.Num(q, "width", 0);
            int length = (int)Json.Num(q, "length", 0);
            int limit = (int)Json.Num(q, "limit", 50);
            var list = new List<object>();
            uint n = (uint)PrefabCollection<BuildingInfo>.LoadedCount();
            for (uint i = 0; i < n && list.Count < limit; i++)
            {
                var b = PrefabCollection<BuildingInfo>.GetLoaded(i);
                if (b == null || b.m_class == null)
                    continue;
                if (service != "" && b.m_class.m_service.ToString() != service)
                    continue;
                if (sub != "" && b.m_class.m_subService.ToString() != sub)
                    continue;
                if (level > 0 && (int)b.m_class.m_level + 1 != level)
                    continue;
                if (width > 0 && b.m_cellWidth != width)
                    continue;
                if (length > 0 && b.m_cellLength != length)
                    continue;
                list.Add(Describe(b));
            }
            return Host.Obj("templates", list);
        }

        internal static Dictionary<string, object> Describe(BuildingInfo b)
        {
            var d = Host.Obj(
                "name", b.name,
                "service", b.m_class == null ? null : b.m_class.m_service.ToString(),
                "sub_service", b.m_class == null ? null : b.m_class.m_subService.ToString(),
                "level", b.m_class == null ? 0 : (int)b.m_class.m_level + 1,
                "class", b.m_class == null ? null : b.m_class.name,
                "ai", b.m_buildingAI == null ? null : b.m_buildingAI.GetType().Name,
                "cells", new object[] { b.m_cellWidth, b.m_cellLength },
                "placement", b.m_placementStyle.ToString(),
                "zoning", b.m_zoningMode.ToString()
            );
            var mf = b.GetComponent<MeshFilter>();
            if (mf != null && mf.sharedMesh != null)
                d["mesh"] = MeshInfo(mf.sharedMesh);
            var mr = b.GetComponent<MeshRenderer>();
            if (mr != null && mr.sharedMaterial != null)
                d["material"] = MaterialInfo(mr.sharedMaterial);
            if (b.m_lodObject != null)
            {
                var lf = b.m_lodObject.GetComponent<MeshFilter>();
                var lr = b.m_lodObject.GetComponent<MeshRenderer>();
                d["lod"] = Host.Obj(
                    "mesh", lf == null || lf.sharedMesh == null ? null : MeshInfo(lf.sharedMesh),
                    "material", lr == null || lr.sharedMaterial == null ? null : MaterialInfo(lr.sharedMaterial)
                );
            }
            if (b.m_generatedInfo != null)
            {
                var g = b.m_generatedInfo;
                d["generated_size"] = new object[] { g.m_size.x, g.m_size.y, g.m_size.z };
            }
            return d;
        }

        internal static Dictionary<string, object> MeshInfo(Mesh m)
        {
            var bb = m.bounds;
            return Host.Obj(
                "name", m.name,
                "vertices", m.vertexCount,
                "triangles", m.triangles.Length / 3,
                "min", new object[] { bb.min.x, bb.min.y, bb.min.z },
                "max", new object[] { bb.max.x, bb.max.y, bb.max.z },
                "size", new object[] { bb.size.x, bb.size.y, bb.size.z }
            );
        }

        internal static Dictionary<string, object> MaterialInfo(Material m)
        {
            var tex = new Dictionary<string, object>();
            foreach (var prop in new[] { "_MainTex", "_XYSMap", "_ACIMap", "_XYCAMap", "_CCCMap" })
            {
                if (!m.HasProperty(prop))
                    continue;
                var t = m.GetTexture(prop);
                tex[prop] = t == null ? null : (object)new object[] { t.width, t.height, (t as Texture2D) == null ? "" : ((Texture2D)t).format.ToString() };
            }
            return Host.Obj("shader", m.shader == null ? null : m.shader.name, "textures", tex);
        }

        static string SavePath(string saveName)
        {
            // SaveAssetPanel.GetSavePathName, so the job reports the file the game wrote.
            return (string)Reflect.CallStatic(typeof(SaveAssetPanel), "GetSavePathName", saveName);
        }

        static Dictionary<string, object> Build(Dictionary<string, object> q)
        {
            string name = Json.Str(q, "name", "");
            string templateName = Json.Str(q, "template", "");
            if (name == "" || templateName == "")
                throw new Exception("asset_build needs {name, template}");
            var template = PrefabCollection<BuildingInfo>.FindLoaded(templateName);
            if (template == null)
                throw new Exception("no building template '" + templateName + "'; `templates` lists them");
            string importDir = AssetImporterAssetImport.assetImportPath;
            string file = name + ".fbx";
            if (!File.Exists(Path.Combine(importDir, file)))
                throw new Exception(file + " is not in " + importDir);
            var cells = q.ContainsKey("cells") ? (List<object>)q["cells"] : null;
            string assetName = Json.Str(q, "asset_name", name);
            string saveName = Json.Str(q, "save_name", name);
            string savePath = SavePath(saveName);
            if (File.Exists(savePath))
            {
                if (!Json.Bool(q, "overwrite", false))
                    throw new Exception(savePath + " exists; pass overwrite:true or another save_name");
                File.Delete(savePath);
            }
            var job = Jobs.Start("asset_build", j => BuildSteps(j, q, template, importDir, name, cells, assetName, saveName, savePath));
            return Host.Obj("job", job.Id, "save_path", savePath);
        }

        static IEnumerator BuildSteps(
            Job job,
            Dictionary<string, object> q,
            BuildingInfo template,
            string importDir,
            string name,
            List<object> cells,
            string assetName,
            string saveName,
            string savePath
        )
        {
            int errorsBefore;
            Host.ErrorSnapshot(out errorsBefore);
            job.Result["template"] = Describe(template);
            job.Result["import_dir"] = importDir;
            job.Result["save_path"] = savePath;

            job.Note("waiting for the import wizard");
            AssetImporterWizard wizard = null;
            yield return Jobs.Until(
                () =>
                {
                    wizard = UIView.library.Get<AssetImporterWizard>("AssetImporterPanel");
                    return wizard != null && wizard.component.isVisible;
                },
                120,
                "the Asset Editor's import wizard"
            );

            // Asset type "Building" -> template -> import panel, as the wizard's Continue buttons do.
            job.Note("template " + template.name);
            Reflect.Set(wizard.assetTemplatePanel, "m_SelectedPrefabInfo", template); // its setter is private
            var importPanel = wizard.assetImportPanel;
            importPanel.OnEnter();
            wizard.GoTo(importPanel);
            yield return Jobs.Frames(5);

            var fileList = Reflect.Get<UIListBox>(importPanel, "m_FileList");
            string file = name + ".fbx";
            int index = -1;
            yield return Jobs.Until(
                () =>
                {
                    index = fileList.items == null ? -1 : Array.IndexOf(fileList.items, file);
                    return index >= 0;
                },
                30,
                file + " in the import list"
            );
            job.Note("importing " + file);
            fileList.selectedIndex = index; // OnFileSelectionChanged -> ImportAsset.Import

            ImportAsset current = null;
            yield return Jobs.Until(
                () =>
                {
                    current = Reflect.Get<ImportAsset>(importPanel, "m_CurrentAsset");
                    return current != null && !current.IsLoadingModel && !current.IsLoadingTextures && current.TextureLoadingFinished;
                },
                300,
                "the model and its textures to load"
            );
            if (!current.ReadyForEditing || current.Object == null)
                throw new Exception("the game could not read " + file + " (see the game log)");
            yield return Jobs.Frames(3); // the panel applies its default scale once the model is in

            float scale = (float)Json.Num(q, "scale", 1);
            Reflect.Get<UITextField>(importPanel, "m_Scale").text = scale.ToString(CultureInfo.InvariantCulture);
            importPanel.ApplyTransform();
            var mesh = current.Object.GetComponent<MeshFilter>().sharedMesh;
            job.Result["imported_mesh"] = MeshInfo(mesh);
            job.Result["default_scale"] = current.CalculateDefaultScale();
            job.Result["lod_from_file"] = !Reflect.Get<bool>(current, "m_NeedToBuildLODModel");
            job.Result["lod_textures_from_file"] = !Reflect.Get<bool>(current, "m_NeedToBakeLODTextures");
            if (q.ContainsKey("expect_size"))
            {
                // Catch unit and axis slips here, not in the game: x across, y up, z deep.
                var want = (List<object>)q["expect_size"];
                var got = mesh.bounds.size;
                var have = new[] { got.x, got.y, got.z };
                for (int i = 0; i < 3; i++)
                {
                    float w = Convert.ToSingle(want[i]);
                    if (Mathf.Abs(have[i] - w) > 0.03f * w + 0.05f)
                        throw new Exception(
                            string.Format(
                                CultureInfo.InvariantCulture,
                                "imported mesh is {0:F2} x {1:F2} x {2:F2} m (x, y up, z); expected {3:F2} x {4:F2} x {5:F2}",
                                got.x, got.y, got.z, want[0], want[1], want[2]
                            )
                        );
                }
            }

            job.Note("continue: finalize import");
            var cont = Reflect.Get<UIButton>(importPanel, "m_ContinueButton");
            yield return Jobs.Until(() => cont.isEnabled, 60, "the import panel's Continue button");
            cont.SimulateClick();
            yield return Jobs.Frames(2);
            yield return Jobs.Until(
                () => LoadSaveStatus.activeTask == null || LoadSaveStatus.activeTask.completedOrFailed,
                600,
                "texture compression and LOD tasks"
            );
            yield return Jobs.Frames(2);

            var info = ToolsModifierControl.toolController.m_editPrefabInfo as BuildingInfo;
            if (info == null)
                throw new Exception("the editor has no building after import");
            if (cells != null)
            {
                int w = Convert.ToInt32(cells[0]), l = Convert.ToInt32(cells[cells.Count > 1 ? 1 : 0]);
                int minW, maxW, minL, maxL;
                info.GetWidthRange(out minW, out maxW);
                info.GetLengthRange(out minL, out maxL);
                if (w < minW || w > maxW || l < minL || l > maxL)
                    throw new Exception(string.Format("lot {0}x{1} is outside the template's {2}-{3} x {4}-{5}", w, l, minW, maxW, minL, maxL));
                info.m_cellWidth = w;
                info.m_cellLength = l;
            }
            job.Result["edit_prefab"] = Describe(info);

            job.Note("save panel: snapshots and thumbnails");
            var panel = UIView.library.ShowModal<SaveAssetPanel>("SaveAssetPanel");
            string description = Json.Str(q, "description", "Built by cs1-harness asset_build");
            Func<bool> ready = () =>
            {
                // The panel refills its fields when its snapshot folder changes, so set them each frame.
                Reflect.Get<UITextField>(panel, "m_SaveName").text = saveName;
                Reflect.Get<UITextField>(panel, "m_AssetName").text = assetName;
                Reflect.Get<UITextField>(panel, "m_AssetDesc").text = description;
                return (bool)Reflect.Call(panel, "CheckValid");
            };
            yield return Jobs.Until(ready, 180, "the save panel's compulsory snapshots");
            job.Note("saving " + savePath);
            panel.OnSave();
            yield return Jobs.Frames(2);
            yield return Jobs.Until(() => !SaveAssetPanel.isSaving && File.Exists(savePath), 300, "the package write");

            int errorsAfter;
            var errors = Host.ErrorSnapshot(out errorsAfter);
            var fresh = new List<object>();
            for (int i = Math.Min(errorsBefore, errors.Length); i < errors.Length; i++)
                fresh.Add(errors[i]);
            job.Result["errors_during_build"] = fresh;
            job.Result["crp"] = savePath;
            job.Result["crp_bytes"] = new FileInfo(savePath).Length;
            job.Result["prefab_name"] = saveName + "." + assetName + "_Data";

            if (!Json.Bool(q, "keep_import", false))
            {
                var removed = new List<object>();
                foreach (var f in Directory.GetFiles(importDir, name + "*"))
                {
                    string stem = Path.GetFileNameWithoutExtension(f);
                    if (stem == name || stem.StartsWith(name + "_"))
                    {
                        File.Delete(f);
                        removed.Add(Path.GetFileName(f));
                    }
                }
                job.Result["import_files_removed"] = removed;
            }
        }
    }
}
