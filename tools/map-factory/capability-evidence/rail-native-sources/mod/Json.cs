// Minimal JSON for the harness socket (.NET 3.5 has none). Objects become
// Dictionary<string, object>, arrays List<object>, numbers double.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace Cs1Harness
{
    public static class Json
    {
        public static object Parse(string text)
        {
            int i = 0;
            object v = Value(text, ref i);
            Skip(text, ref i);
            if (i != text.Length)
                throw new FormatException("trailing characters at " + i);
            return v;
        }

        static void Skip(string s, ref int i)
        {
            while (i < s.Length && char.IsWhiteSpace(s[i]))
                i++;
        }

        static object Value(string s, ref int i)
        {
            Skip(s, ref i);
            if (i >= s.Length)
                throw new FormatException("unexpected end");
            char c = s[i];
            if (c == '{')
            {
                var d = new Dictionary<string, object>();
                i++;
                Skip(s, ref i);
                if (s[i] == '}')
                {
                    i++;
                    return d;
                }
                while (true)
                {
                    Skip(s, ref i);
                    string key = String(s, ref i);
                    Skip(s, ref i);
                    if (s[i++] != ':')
                        throw new FormatException("expected ':' at " + (i - 1));
                    d[key] = Value(s, ref i);
                    Skip(s, ref i);
                    char n = s[i++];
                    if (n == '}')
                        return d;
                    if (n != ',')
                        throw new FormatException("expected ',' or '}' at " + (i - 1));
                }
            }
            if (c == '[')
            {
                var a = new List<object>();
                i++;
                Skip(s, ref i);
                if (s[i] == ']')
                {
                    i++;
                    return a;
                }
                while (true)
                {
                    a.Add(Value(s, ref i));
                    Skip(s, ref i);
                    char n = s[i++];
                    if (n == ']')
                        return a;
                    if (n != ',')
                        throw new FormatException("expected ',' or ']' at " + (i - 1));
                }
            }
            if (c == '"')
                return String(s, ref i);
            if (Literal(s, ref i, "true"))
                return true;
            if (Literal(s, ref i, "false"))
                return false;
            if (Literal(s, ref i, "null"))
                return null;
            int start = i;
            while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0)
                i++;
            if (start == i)
                throw new FormatException("unexpected '" + c + "' at " + i);
            return double.Parse(s.Substring(start, i - start), NumberStyles.Float, CultureInfo.InvariantCulture);
        }

        static bool Literal(string s, ref int i, string word)
        {
            if (string.CompareOrdinal(s, i, word, 0, word.Length) != 0)
                return false;
            i += word.Length;
            return true;
        }

        static string String(string s, ref int i)
        {
            if (s[i] != '"')
                throw new FormatException("expected string at " + i);
            i++;
            var b = new StringBuilder();
            while (true)
            {
                char c = s[i++];
                if (c == '"')
                    return b.ToString();
                if (c != '\\')
                {
                    b.Append(c);
                    continue;
                }
                char e = s[i++];
                switch (e)
                {
                    case 'n': b.Append('\n'); break;
                    case 't': b.Append('\t'); break;
                    case 'r': b.Append('\r'); break;
                    case 'b': b.Append('\b'); break;
                    case 'f': b.Append('\f'); break;
                    case 'u':
                        b.Append((char)int.Parse(s.Substring(i, 4), NumberStyles.HexNumber));
                        i += 4;
                        break;
                    default: b.Append(e); break;
                }
            }
        }

        public static string Write(object v)
        {
            var b = new StringBuilder();
            Emit(b, v);
            return b.ToString();
        }

        static void Emit(StringBuilder b, object v)
        {
            if (v == null)
                b.Append("null");
            else if (v is string)
                Quote(b, (string)v);
            else if (v is bool)
                b.Append((bool)v ? "true" : "false");
            else if (v is float)
                Number(b, (float)v);
            else if (v is double)
                Number(b, (double)v);
            else if (v is int || v is uint || v is long || v is ulong || v is short || v is ushort || v is byte || v is sbyte)
                b.Append(Convert.ToString(v, CultureInfo.InvariantCulture));
            else if (v is IDictionary)
            {
                b.Append('{');
                bool first = true;
                foreach (DictionaryEntry kv in (IDictionary)v)
                {
                    if (!first)
                        b.Append(',');
                    first = false;
                    Quote(b, kv.Key.ToString());
                    b.Append(':');
                    Emit(b, kv.Value);
                }
                b.Append('}');
            }
            else if (v is IEnumerable)
            {
                b.Append('[');
                bool first = true;
                foreach (object x in (IEnumerable)v)
                {
                    if (!first)
                        b.Append(',');
                    first = false;
                    Emit(b, x);
                }
                b.Append(']');
            }
            else
                Quote(b, v.ToString());
        }

        static void Number(StringBuilder b, double d)
        {
            if (double.IsNaN(d) || double.IsInfinity(d))
                b.Append("null");
            else
                b.Append(d.ToString("R", CultureInfo.InvariantCulture));
        }

        static void Quote(StringBuilder b, string s)
        {
            b.Append('"');
            foreach (char c in s)
            {
                if (c == '"' || c == '\\')
                    b.Append('\\').Append(c);
                else if (c < ' ')
                    b.Append("\\u").Append(((int)c).ToString("x4"));
                else
                    b.Append(c);
            }
            b.Append('"');
        }

        public static string Str(Dictionary<string, object> q, string key, string fallback)
        {
            object v;
            return q.TryGetValue(key, out v) && v != null ? v.ToString() : fallback;
        }

        public static double Num(Dictionary<string, object> q, string key, double fallback)
        {
            object v;
            return q.TryGetValue(key, out v) && v != null ? Convert.ToDouble(v, CultureInfo.InvariantCulture) : fallback;
        }

        public static bool Bool(Dictionary<string, object> q, string key, bool fallback)
        {
            object v;
            return q.TryGetValue(key, out v) && v is bool ? (bool)v : fallback;
        }
    }
}
