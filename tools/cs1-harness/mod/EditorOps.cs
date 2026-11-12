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
            Host.Register("asset_editor", Needs.MainMenu, "open the Asset Editor on a new asset: {theme, safe_readback (default true)}", OpenEditor);
            Host.Register("templates", Needs.AssetEditor, "building templates: {service, sub_service, level, width, length, limit}", Templates);
            Host.Register(
                "asset_build",
                Needs.AssetEditor,
                "job: import <name>.fbx (+ <name>_lod.fbx and maps) from Addons/Import onto a building template, "
                    + "set the lot, save a .crp: {name, template, cells:[w,l], scale, expect_size:[x,y,z], "
                    + "asset_name, save_name, description, overwrite, keep_import, color_variations (default false), stepwise}",
                Build
            );
            Host.Register("job", Needs.Any, "the current or last job: state, step, log, result", q => Jobs.Status());
            Host.Register("safe_readback", Needs.Any, "read textures back through Unity instead of the game's native path (on for asset_editor; see Readback.cs)", q => { Readback.Install(); return Host.Obj("installed", Readback.Installed); });
            Host.Register("image_check", Needs.Any, "run the game's native image path on one file, one step at a time: {path, step: load|compress|upload|readback|all}", ImageCheck);
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

        // Mirrors NewAssetBuiltinThemePanel.OnCreate, which loads GetListingData: the theme's
        // assetRef. Loading the metadata asset itself fails with "File format version not supported".
        static Dictionary<string, object> OpenEditor(Dictionary<string, object> q)
        {
            string want = Json.Str(q, "theme", "Sunny");
            Package.Asset theme = null; // the theme's map data (MetaData.assetRef), as the panel's listing holds
            var seen = new List<string>();
            foreach (var a in PackageManager.FilterAssets(UserAssetType.SystemMapMetaData))
            {
                if (a == null || !a.isEnabled)
                    continue;
                var m = a.Instantiate<SystemMapMetaData>();
                seen.Add(m.environment);
                if (string.Equals(m.environment, want, StringComparison.OrdinalIgnoreCase))
                    theme = m.assetRef;
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
            if (Json.Bool(q, "safe_readback", true))
                Readback.Install();
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
            int bodyVertices, bodyTriangles;
            var body = AuthoredBounds(m, out bodyVertices, out bodyTriangles);
            return Host.Obj(
                "name", m.name,
                "vertices", m.vertexCount,
                "triangles", m.triangles.Length / 3,
                "min", new object[] { bb.min.x, bb.min.y, bb.min.z },
                "max", new object[] { bb.max.x, bb.max.y, bb.max.z },
                "size", new object[] { bb.size.x, bb.size.y, bb.size.z },
                "authored", Host.Obj(
                    "vertices", bodyVertices, "triangles", bodyTriangles,
                    "min", new object[] { body.min.x, body.min.y, body.min.z },
                    "max", new object[] { body.max.x, body.max.y, body.max.z },
                    "size", new object[] { body.size.x, body.size.y, body.size.z }
                ),
                "generated_basement_triangles", m.triangles.Length / 3 - bodyTriangles
            );
        }

        // BuildingInfoBase.CalculateGeneratedInfo marks original vertices alpha=0,
        // generated basement vertices alpha=255, and extends renderer bounds to -16 m.
        // Validate the actual authored body, not that culling envelope; keep both in receipts.
        static Bounds AuthoredBounds(Mesh mesh, out int vertexCount, out int triangleCount)
        {
            var vertices = mesh.vertices;
            var colors = mesh.colors32;
            bool marked = colors.Length == vertices.Length && Array.Exists(colors, c => c.a == 0);
            var included = new bool[vertices.Length];
            var bounds = new Bounds();
            vertexCount = 0;
            for (int i = 0; i < vertices.Length; i++)
            {
                included[i] = !marked || colors[i].a != byte.MaxValue;
                if (!included[i])
                    continue;
                if (vertexCount++ == 0)
                    bounds = new Bounds(vertices[i], Vector3.zero);
                else
                    bounds.Encapsulate(vertices[i]);
            }
            triangleCount = 0;
            var indices = mesh.triangles;
            for (int i = 0; i < indices.Length; i += 3)
                if (included[indices[i]] && included[indices[i + 1]] && included[indices[i + 2]])
                    triangleCount++;
            return bounds;
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

        // Bisects native crashes in the importer's texture path (Image load, DXT compression,
        // GPU upload, read-back) on this host's GPU stack. Each step is logged before it runs.
        static readonly List<object> Kept = new List<object>();

        static Dictionary<string, object> ImageCheck(Dictionary<string, object> q)
        {
            if (Json.Str(q, "step", "") == "gc")
            {
                Kept.Clear();
                GC.Collect();
                GC.WaitForPendingFinalizers();
                return Host.Obj("gc", true);
            }
            string path = Json.Str(q, "path", "");
            string upTo = Json.Str(q, "step", "all");
            var done = new List<object>();
            Action<string> mark = step =>
            {
                Debug.Log("[Cs1Harness] image_check " + step + " " + path);
                Console.Out.Flush();
            };
            if (upTo == "raw")
            {
                mark("raw: upload uncompressed");
                var t = new ColossalFramework.Importers.Image(path).CreateTexture(Json.Bool(q, "linear", false));
                mark("raw: read back " + t.format);
                var b = new ColossalFramework.Importers.Image(t);
                mark("raw: read back done " + b.format);
                if (Json.Bool(q, "destroy", false))
                    UnityEngine.Object.Destroy(t);
                if (Json.Bool(q, "keep", false))
                    Kept.Add(b);
                return Host.Obj("raw", new object[] { b.width, b.height, b.format.ToString() });
            }
            if (upTo == "exact")
            {
                // AssetImporterTextureLoader.CompressTexture's own sequence on a texture made from the file.
                mark("exact: upload");
                var src = new ColossalFramework.Importers.Image(path).CreateTexture(Json.Bool(q, "linear", false));
                mark("exact: read back " + src.format);
                var im = new ColossalFramework.Importers.Image(src);
                mark("exact: convert " + im.format + " " + im.width + "x" + im.height);
                im.Convert(TextureFormat.RGB24);
                mark("exact: compress on the task distributor");
                ColossalFramework.Threading.ThreadHelper.taskDistributor.Dispatch(() => im.Compress()).Wait();
                mark("exact: create texture");
                var outTex = im.CreateTexture(Json.Bool(q, "linear", false));
                UnityEngine.Object.Destroy(src);
                return Host.Obj("exact", new object[] { outTex.width, outTex.height, outTex.format.ToString() });
            }
            mark("load");
            var img = new ColossalFramework.Importers.Image(path);
            done.Add(Host.Obj("load", new object[] { img.width, img.height, img.format.ToString() }));
            if (upTo == "load")
                return Host.Obj("steps", done);
            mark("convert");
            img.Convert(TextureFormat.RGB24);
            mark(Json.Bool(q, "thread", false) ? "compress on the task distributor" : "compress");
            if (Json.Bool(q, "thread", false))
                ColossalFramework.Threading.ThreadHelper.taskDistributor.Dispatch(() => img.Compress()).Wait();
            else
                img.Compress();
            done.Add(Host.Obj("compress", img.format.ToString()));
            if (upTo == "compress")
                return Host.Obj("steps", done);
            mark("upload");
            var tex = img.CreateTexture(false);
            done.Add(Host.Obj("upload", new object[] { tex.width, tex.height, tex.format.ToString() }));
            if (upTo == "upload")
                return Host.Obj("steps", done);
            mark("readback");
            var back = new ColossalFramework.Importers.Image(tex);
            done.Add(Host.Obj("readback", new object[] { back.width, back.height, back.format.ToString() }));
            UnityEngine.Object.Destroy(tex);
            return Host.Obj("steps", done);
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
            job.Result["modal_at_start"] = Host.ModalStack();
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
                int bodyVertices, bodyTriangles;
                var got = AuthoredBounds(mesh, out bodyVertices, out bodyTriangles).size;
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

            job.Result["modal_before_continue"] = Host.ModalStack();
            job.Note("continue: finalize import");
            var cont = Reflect.Get<UIButton>(importPanel, "m_ContinueButton");
            yield return Jobs.Until(() => cont.isEnabled, 60, "the import panel's Continue button");
            if (Json.Bool(q, "stepwise", false))
            {
                // AssetImporterAssetImport.OnContinue, one step per frame with a log line each,
                // to find which step a native crash comes from.
                job.Note("stepwise: apply transform");
                current.ApplyTransform(new Vector3(scale, scale, scale), Vector3.zero, false);
                yield return Jobs.Frames(30);
                // ImportAsset.FinalizeImport, call by call.
                job.Note("stepwise: FinalizeLOD (LOD material and textures)");
                Reflect.Call(current, "FinalizeLOD");
                yield return Jobs.Frames(30);
                job.Note("stepwise: CompressTextures");
                Reflect.Call(current, "CompressTextures");
                yield return Jobs.Frames(30);
                var wrapper = new MultiAsyncTaskWrapper(
                    Reflect.Get<List<string>>(current, "m_TaskNames"),
                    Reflect.Get<List<ColossalFramework.Threading.Task[]>>(current, "m_Tasks")
                );
                Reflect.Set(current, "m_TaskWrapper", wrapper);
                LoadSaveStatus.activeTask = wrapper;
                job.Note("stepwise: InitializeObject");
                Reflect.Call(current, "InitializeObject");
                yield return Jobs.Frames(30);
                job.Note("stepwise: CreateThumbnails");
                AssetImporterThumbnails.CreateThumbnails(
                    current.Object,
                    Path.Combine(importDir, name),
                    Reflect.Get<PreviewCamera>(importPanel, "m_PreviewCamera")
                );
                yield return Jobs.Frames(30);
                job.Note("stepwise: waiting for tasks");
                yield return Jobs.Until(() => LoadSaveStatus.activeTask == null || LoadSaveStatus.activeTask.completedOrFailed, 600, "tasks");
                yield return Jobs.Frames(30);
                job.Note("stepwise: hand the prefab to the editor");
                var old = ToolsModifierControl.toolController.m_editPrefabInfo;
                if (old != null && !(old is NetInfo))
                {
                    ToolsModifierControl.toolController.m_editPrefabInfo = null;
                    UnityEngine.Object.DestroyImmediate(old.gameObject);
                }
                ToolsModifierControl.toolController.m_editPrefabInfo = current.Object.GetComponent<PrefabInfo>();
                ToolsModifierControl.toolController.m_templatePrefabInfo = current.TemplateObject.GetComponent<PrefabInfo>();
                yield return Jobs.Frames(30);
                job.Note("stepwise: close the wizard");
                wizard.Complete();
                yield return Jobs.Frames(30);
                job.Note("stepwise: done");
            }
            else
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
            if (!Json.Bool(q, "color_variations", false))
            {
                // The model's own colours: no tint from the template's variation colours. With
                // variations off the game uses the material's _Color, which the template set,
                // so every colour the shader multiplies by goes to white (LOD included).
                var tint = new Dictionary<string, object>();
                info.m_useColorVariations = false;
                var renderers = new List<Renderer> { info.GetComponent<MeshRenderer>() };
                if (info.m_lodObject != null)
                    renderers.Add(info.m_lodObject.GetComponent<MeshRenderer>());
                foreach (var r in renderers)
                {
                    if (r == null || r.sharedMaterial == null)
                        continue;
                    foreach (var prop in new[] { "_Color", "_ColorV0", "_ColorV1", "_ColorV2", "_ColorV3" })
                        if (r.sharedMaterial.HasProperty(prop))
                        {
                            var c = r.sharedMaterial.GetColor(prop);
                            tint[r.gameObject.name + prop] = new object[] { c.r, c.g, c.b, c.a };
                            r.sharedMaterial.SetColor(prop, Color.white);
                        }
                }
                job.Result["template_colours_replaced"] = tint;
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
