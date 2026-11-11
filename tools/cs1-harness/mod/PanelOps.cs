using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using ColossalFramework;
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
                "select/inspect native New Game listing + actual resource bars: {path, select?, bars_only?, screenshot?}; or {close:true}", Inspect);
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

        static T Field<T>(NewGamePanel panel, string name)
        {
            var field = typeof(NewGamePanel).GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field == null) throw new Exception("native NewGamePanel field missing: " + name);
            return (T)field.GetValue(panel);
        }

        static Dictionary<string, object> Bar(NewGamePanel panel, string barField, string iconField,
            string exponentField, string animation, uint amount, float denominator)
        {
            var bar = Field<UIProgressBar>(panel, barField);
            var icon = Field<UISprite>(panel, iconField);
            if (bar == null || icon == null) throw new Exception("native resource UI is unavailable: " + barField);
            float exponent = Field<float>(panel, exponentField);
            // Same native expression as OnMapSelectionChanged; observe only.
            float target = denominator > 0f ? Mathf.Pow((float)amount / denominator, exponent) : 0f;
            return Host.Obj("component", bar.name, "value", bar.value, "min_value", bar.minValue, "max_value", bar.maxValue,
                "normalized_target", target, "target_value", Mathf.Clamp(target, bar.minValue, bar.maxValue),
                "amount", amount, "denominator", denominator, "exponent", exponent,
                "no_resource_visible", icon.isVisible, "expected_no_resource", amount == 0,
                "visible", bar.isVisible, "animating", ValueAnimator.IsAnimating(animation));
        }

        static Dictionary<string, object> Bars(NewGamePanel panel, MapMetaData meta)
        {
            float max = meta.maxResourceAmount;
            return Host.Obj("schema", 1, "source", "native UIProgressBar.value / NewGamePanel resource targets",
                "frame", Time.frameCount, "realtime", Time.realtimeSinceStartup,
                "bars", Host.Obj(
                    "oil", Bar(panel, "m_OilResources", "m_OilNoResources", "m_OilExponent", "NewGameOil", meta.oilAmount, max),
                    "ore", Bar(panel, "m_OreResources", "m_OreNoResources", "m_OreExponent", "NewGameOre", meta.oreAmount, max),
                    "forest", Bar(panel, "m_ForestryResources", "m_ForestryNoResources", "m_ForestryExponent", "NewGameForest", meta.forestAmount, max),
                    "fertility", Bar(panel, "m_FertilityResources", "m_FertilityNoResources", "m_FarmingExponent", "NewGameFertility", meta.fertileLandAmount, max),
                    "water", Bar(panel, "m_WaterResources", "m_WaterNoResources", "m_WaterExponent", "NewGameWater", meta.waterAmount, max)));
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
            bool refreshed = false;
            if (Json.Bool(q, "select", false))
            {
                // UIListBox's same-index setter emits no selection event. Explicit
                // selection refreshes via the native event, never by setting bars.
                refreshed = list.selectedIndex == found;
                if (refreshed) list.selectedIndex = -1;
                list.selectedIndex = found;
            }
            if (list.selectedIndex != found) throw new Exception("requested map is not selected in NewGamePanel");
            var meta = (MapMetaData)Listing(panel, "GetListingMetaData", found);
            var payload = (Package.Asset)Listing(panel, "GetListingData", found);
            var snapshot = panel.Find<UITextureSprite>("SnapShot");
            var resources = Host.Obj("maxResourceAmount", meta.maxResourceAmount,
                "oilAmount", meta.oilAmount, "oreAmount", meta.oreAmount, "forestAmount", meta.forestAmount,
                "fertileLandAmount", meta.fertileLandAmount, "waterAmount", meta.waterAmount);
            var bars = Bars(panel, meta);
            if (Json.Bool(q, "bars_only", false))
                return Host.Obj("source", "native NewGamePanel", "path", path, "selected_index", found,
                    "map_name", meta.mapName, "resources", resources, "resource_bars", bars);
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
                "selection_refreshed", refreshed, "resource_bars", bars,
                "resources", resources, "connections", connections,
                "imageRef", TextureRef(meta.imageRef), "steamPreviewRef", TextureRef(meta.steamPreviewRef),
                "snapshot_texture_present", snapshot.texture != null,
                "author_label", panel.Find<UILabel>("Author").text,
                "author_visible", panel.Find<UILabel>("Author").isVisible,
                "buildable_label", panel.Find<UILabel>("BuildableArea").text);
        }
    }
}
