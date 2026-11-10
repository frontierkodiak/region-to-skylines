using System;
using System.Collections.Generic;
using ColossalFramework.UI;
using UnityEngine;

namespace Cs1Harness
{
    // Dialogs that sit in front of the game: list them, and press a named button
    // the way a player would. Which dialogs to answer, and how, is decided on the
    // Python side (dialogs.py); this module only reports and clicks.
    public static class DialogOps
    {
        public const string Advisor = "TutorialAdvisorPanel";

        public static void Register()
        {
            Host.Register("dialogs", Needs.Any, "visible dialogs: name, modal, texts, buttons", q => List());
            Host.Register("dialog_click", Needs.Any, "press a dialog's button: {dialog, button (name or text)}", Click);
        }

        static Dictionary<string, object> Describe(string name, UIComponent c, bool modal)
        {
            var texts = new List<object>();
            foreach (var l in c.GetComponentsInChildren<UILabel>())
                if (l.isVisible && !string.IsNullOrEmpty(l.text) && texts.Count < 8)
                    texts.Add(l.text.Length > 200 ? l.text.Substring(0, 200) : l.text);
            var buttons = new List<object>();
            foreach (var b in c.GetComponentsInChildren<UIButton>())
                if (b.isVisible)
                    buttons.Add(Host.Obj("name", b.name, "text", b.text, "enabled", b.isEnabled));
            return Host.Obj("name", name, "component", c.name, "modal", modal, "texts", texts, "buttons", buttons);
        }

        static Dictionary<string, object> List()
        {
            var found = new List<object>();
            var seen = new HashSet<UIComponent>();
            UIComponent modal = UIView.HasModalInput() ? UIView.GetModalComponent() : null;
            var library = UIView.library;
            if (library != null && library.m_DynamicPanels != null)
                foreach (var info in library.m_DynamicPanels)
                {
                    UIComponent c = info == null ? null : info.instance;
                    if (c == null || !c.isVisible || seen.Contains(c))
                        continue;
                    seen.Add(c);
                    found.Add(Describe(info.name, c, c == modal));
                }
            if (modal != null && !seen.Contains(modal))
                found.Add(Describe(modal.name, modal, true));
            var advisor = TutorialAdvisorPanel.instance;
            if (advisor != null && advisor.isVisible)
                found.Add(Describe(Advisor, advisor.component, false));
            return Host.Obj("dialogs", found, "modal_input", UIView.HasModalInput());
        }

        static UIComponent Find(string dialog)
        {
            if (dialog == Advisor)
            {
                var a = TutorialAdvisorPanel.instance;
                return a != null && a.isVisible ? a.component : null;
            }
            var library = UIView.library;
            if (library != null && library.m_DynamicPanels != null)
                foreach (var info in library.m_DynamicPanels)
                    if (info != null && info.name == dialog && info.instance != null && info.instance.isVisible)
                        return info.instance;
            var modal = UIView.HasModalInput() ? UIView.GetModalComponent() : null;
            return modal != null && modal.name == dialog ? modal : null;
        }

        static Dictionary<string, object> Click(Dictionary<string, object> q)
        {
            string dialog = Json.Str(q, "dialog", "");
            string wanted = Json.Str(q, "button", "");
            var c = Find(dialog);
            if (c == null)
                throw new Exception("dialog '" + dialog + "' is not showing");
            if (dialog == Advisor && (wanted == "close" || wanted == ""))
            {
                // What Escape does in game.
                TutorialAdvisorPanel.instance.OnClose();
                return Host.Obj("dialog", dialog, "pressed", "close");
            }
            foreach (var b in c.GetComponentsInChildren<UIButton>())
            {
                if (!b.isVisible || !b.isEnabled)
                    continue;
                if (string.Equals(b.name, wanted, StringComparison.OrdinalIgnoreCase)
                    || string.Equals((b.text ?? "").Trim(), wanted, StringComparison.OrdinalIgnoreCase))
                {
                    b.SimulateClick();
                    return Host.Obj("dialog", dialog, "pressed", b.name, "text", b.text);
                }
            }
            throw new Exception("dialog '" + dialog + "' has no enabled button '" + wanted + "'");
        }
    }
}
