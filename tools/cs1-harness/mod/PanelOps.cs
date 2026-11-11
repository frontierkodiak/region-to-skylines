using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using ColossalFramework.Packaging;
using ColossalFramework.UI;
using UnityEngine;

namespace Cs1Harness
{
    // Observe the actual NewGamePanel listing, not merely PackageManager's maps.
    public static class PanelOps
    {
        public static void Register()
        {
            Host.Register("new_game_panel", Needs.MainMenu,
                "select/inspect native New Game listing: {path, select?, screenshot?}; or {close:true}", Inspect);
        }

        static object Listing(NewGamePanel panel, string method, params object[] args)
        {
            var info = typeof(LoadSavePanelBase<MapMetaData>).GetMethod(method,
                BindingFlags.Instance | BindingFlags.NonPublic);
            if (info == null) throw new Exception("native listing method unavailable: " + method);
            return info.Invoke(panel, args);
        }

        static Dictionary<string, object> TextureRef(Package.Asset asset)
        {
            if (asset == null) return Host.Obj("name", null, "resolved", false);
            Texture texture = null;
            try
            {
                texture = asset.Instantiate<Texture>();
                return Host.Obj("name", asset.name, "resolved", texture != null,
                    "width", texture == null ? 0 : texture.width, "height", texture == null ? 0 : texture.height);
            }
            // Package.Instantiate deserializes into Image.CreateTexture -> new
            // Texture2D; CacheAsset caches bytes only. This is not the UI snapshot.
            finally { if (texture != null) UnityEngine.Object.Destroy(texture); }
        }

        static Dictionary<string, object> Inspect(Dictionary<string, object> q)
        {
            if (Json.Bool(q, "close", false))
            {
                UIView.library.Hide("NewGamePanel");
                return Host.Obj("closed", true);
            }
            string path = Path.GetFullPath(Json.Str(q, "path", ""));
            if (Json.Bool(q, "select", false)) UIView.library.ShowModal("NewGamePanel");
            // The library root has NewGameMainPanel; the map listing controller
            // lives on its Maps tab, not on that root's GameObject.
            var root = UIView.library.Get("NewGamePanel");
            if (root == null || !root.isVisible) throw new Exception("native New Game modal is not visible");
            if (Json.Bool(q, "select", false))
            {
                var chooseMap = root.Find<UIButton>("TabChooseMap");
                if (chooseMap == null || !chooseMap.isEnabled) throw new Exception("native Maps tab is unavailable");
                chooseMap.SimulateClick();
            }
            var listings = root.GetComponentsInChildren<NewGamePanel>(true);
            if (listings.Length != 1) throw new Exception("expected one native NewGamePanel map listing, found " + listings.Length);
            var panel = listings[0];
            if (!panel.GetComponent<UIComponent>().isVisible) throw new Exception("native New Game Maps tab is not visible");
            var list = panel.Find<UIListBox>("MapList");
            int found = -1;
            for (int i = 0; i < (int)Listing(panel, "GetListingCount"); i++)
            {
                string itemPath = (string)Listing(panel, "GetListingPath", i);
                if (string.IsNullOrEmpty(itemPath) || Path.GetFullPath(itemPath) != path) continue;
                if (found != -1) throw new Exception("ambiguous map in New Game listing: " + path);
                found = i;
            }
            if (found < 0) throw new Exception("map absent from native New Game listing: " + path);
            if (Json.Bool(q, "select", false)) list.selectedIndex = found;
            if (list.selectedIndex != found) throw new Exception("requested map is not selected in NewGamePanel");
            var meta = (MapMetaData)Listing(panel, "GetListingMetaData", found);
            var payload = (Package.Asset)Listing(panel, "GetListingData", found);
            var snapshot = panel.Find<UITextureSprite>("SnapShot");
            var resources = Host.Obj("maxResourceAmount", meta.maxResourceAmount,
                "oilAmount", meta.oilAmount, "oreAmount", meta.oreAmount, "forestAmount", meta.forestAmount,
                "fertileLandAmount", meta.fertileLandAmount, "waterAmount", meta.waterAmount);
            var connections = Host.Obj("incomingRoads", meta.incomingRoads, "outgoingRoads", meta.outgoingRoads,
                "incomingTrainTracks", meta.incomingTrainTracks, "outgoingTrainTracks", meta.outgoingTrainTracks,
                "incomingShipPath", meta.incomingShipPath, "outgoingShipPath", meta.outgoingShipPath,
                "incomingPlanePath", meta.incomingPlanePath, "outgoingPlanePath", meta.outgoingPlanePath);
            string shot = Json.Str(q, "screenshot", "");
            if (!string.IsNullOrEmpty(shot))
            {
                if (!Path.IsPathRooted(shot)) throw new Exception("screenshot must be absolute");
                Directory.CreateDirectory(Path.GetDirectoryName(shot));
                if (File.Exists(shot)) File.Delete(shot);
                Application.CaptureScreenshot(shot);
            }
            return Host.Obj("source", "native NewGamePanel", "path", path, "selected_index", found,
                "map_name", meta.mapName, "author", payload.package.packageAuthor,
                "published", meta.isPublished, "buildableArea", meta.buildableArea,
                "resources", resources, "connections", connections,
                "imageRef", TextureRef(meta.imageRef), "steamPreviewRef", TextureRef(meta.steamPreviewRef),
                "snapshot_texture_present", snapshot.texture != null,
                "author_label", panel.Find<UILabel>("Author").text,
                "author_visible", panel.Find<UILabel>("Author").isVisible,
                "buildable_label", panel.Find<UILabel>("BuildableArea").text);
        }
    }
}
