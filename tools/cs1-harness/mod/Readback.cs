using System;
using System.Reflection;
using ColossalFramework.Importers;
using UnityEngine;

namespace Cs1Harness
{
    // The game reads a texture back into an Image natively (Image(Texture) ->
    // CreateImageFromTexture(GetNativeTexturePtr())). Under VirtualGL's EGL back end on
    // blade that read-back corrupts the process, which dies a few seconds later with no
    // trace (PL-880: reproduced with `image_check raw`, in threaded and direct rendering,
    // for RGB24 and RGBA32). The Asset Editor uses it twice: compressing imported textures
    // and serializing every texture into the .crp. So, for Asset Editor sessions, the mod
    // points that one constructor at a managed read-back through Unity (blit to a render
    // texture, ReadPixels), which is the path the game's screenshots already take here.
    //
    // The redirect is the classic CS1 detour: an absolute jump written over the start of
    // the JIT-compiled constructor. x86-64 Mono only; it lasts for this game process.
    public static class Readback
    {
        static bool installed;
        static ConstructorInfo blankCtor;
        static MethodInfo setColors;
        public static int Count;

        public static bool Installed
        {
            get { return installed; }
        }

        public static void Install()
        {
            if (installed)
                return;
            if (IntPtr.Size != 8)
                throw new NotSupportedException("the read-back redirect is x86-64 only");
            var t = typeof(Image);
            blankCtor = t.GetConstructor(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic, null, Type.EmptyTypes, null);
            setColors = t.GetMethod(
                "SetColors",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                null,
                new[] { typeof(int), typeof(int), typeof(TextureFormat), typeof(Color32[]) },
                null
            );
            var from = t.GetConstructor(BindingFlags.Instance | BindingFlags.Public, null, new[] { typeof(Texture) }, null);
            var to = typeof(Readback).GetMethod("FromTexture", BindingFlags.Static | BindingFlags.Public);
            if (blankCtor == null || setColors == null || from == null || to == null)
                throw new MissingMemberException("Image members the read-back redirect needs are missing in this game build");
            Jump(from, to);
            installed = true;
            Debug.Log("[Cs1Harness] Image(Texture) now reads back through Unity (VirtualGL-safe)");
        }

        static unsafe void Jump(MethodBase from, MethodBase to)
        {
            byte* site = (byte*)from.MethodHandle.GetFunctionPointer().ToPointer();
            long target = to.MethodHandle.GetFunctionPointer().ToInt64();
            // mov r11, imm64 ; jmp r11
            site[0] = 0x49;
            site[1] = 0xBB;
            *(long*)(site + 2) = target;
            site[10] = 0x41;
            site[11] = 0xFF;
            site[12] = 0xE3;
        }

        public static int FromCpu;
        public static int FromGpu;

        // Data maps (normal/specular, alpha/colour/illumination, ...) are stored linear; colour
        // maps are sRGB. The game names them by property or channel set.
        static bool LinearData(string name)
        {
            string n = (name ?? "").ToLowerInvariant();
            foreach (var k in new[] { "xys", "aci", "xyca", "apr", "ccc" })
                if (n.Contains(k))
                    return true;
            return false;
        }

        // Stands in for Image..ctor(Texture): `self` is the instance being constructed. Returns
        // the stored texel bytes, as the native read-back does: the texture's CPU copy when it
        // has one, otherwise a GPU read-back that keeps sRGB colour maps encoded.
        public static void FromTexture(Image self, Texture tex)
        {
            var t2d = tex as Texture2D;
            if (t2d == null)
                throw new InvalidCastException("Image can only be created from 2D Texture");
            blankCtor.Invoke(self, null);
            int w = t2d.width, h = t2d.height;
            Color32[] pixels = null;
            try
            {
                pixels = t2d.GetPixels32();
                FromCpu++;
            }
            catch (UnityException)
            {
                // not readable: no CPU copy
            }
            if (pixels == null)
            {
                bool srgb = QualitySettings.activeColorSpace == ColorSpace.Linear && !LinearData(t2d.name);
                var rt = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGB32, srgb ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear);
                var previous = RenderTexture.active;
                Texture2D copy = null;
                try
                {
                    Graphics.Blit(t2d, rt);
                    RenderTexture.active = rt;
                    copy = new Texture2D(w, h, TextureFormat.RGBA32, false, !srgb);
                    copy.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
                    copy.Apply(false);
                    pixels = copy.GetPixels32();
                    FromGpu++;
                }
                finally
                {
                    RenderTexture.active = previous;
                    RenderTexture.ReleaseTemporary(rt);
                    if (copy != null)
                        UnityEngine.Object.Destroy(copy);
                }
            }
            setColors.Invoke(self, new object[] { w, h, TextureFormat.RGBA32, pixels });
            Count++;
        }
    }
}
