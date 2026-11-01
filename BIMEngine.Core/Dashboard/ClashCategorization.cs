using System;
using System.Collections.Generic;
using System.Linq;

namespace BIMEngine.Core.Dashboard
{
    // Presentation-only classification of saved metadata. Never changes issue identity or scan scope.
    public sealed class ClashSideCategories
    {
        private static readonly StringComparer Comparer = StringComparer.OrdinalIgnoreCase;
        private static readonly Dictionary<string, string> ClassGroups = new Dictionary<string, string>(Comparer)
        {
            { "Sanitary", "Sanitary" }, { "Vent", "Sanitary" },
            { "DomesticColdWater", "Water Supply" }, { "DomesticHotWater", "Water Supply" },
            { "FireProtectWet", "Fire Protection" }, { "FireProtectDry", "Fire Protection" },
            { "FireProtectPreaction", "Fire Protection" }, { "FireProtectOther", "Fire Protection" },
            { "SupplyAir", "HVAC" }, { "ReturnAir", "HVAC" }, { "ExhaustAir", "HVAC" },
            { "OtherAir", "HVAC" }, { "HydronicSupply", "HVAC" }, { "HydronicReturn", "HVAC" }
        };
        // Exact project-name fallbacks only; a known Revit classification always wins.
        private static readonly Dictionary<string, string> TypeAliases = new Dictionary<string, string>(Comparer)
        {
            { "PL-Waste", "Sanitary" }, { "PL-Soil", "Sanitary" }
        };

        public string[] Systems { get; }
        public string[] Groups { get; }

        public ClashSideCategories(string category, string systemType, string classification)
        {
            string raw = (systemType ?? "").Trim();
            const string prefix = "Multiple systems: ";
            Systems = Distinct(raw.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                ? raw.Substring(prefix.Length).Split(new[] { " / " }, StringSplitOptions.RemoveEmptyEntries)
                : new[] { raw }).Where(x => x.Length > 0 && !Comparer.Equals(x, "Unassigned")).ToArray();
            if (Systems.Length == 0) Systems = new[] { "Unassigned" };

            if (Comparer.Equals(category, "Structural Framing") || Comparer.Equals(category, "Structural Columns"))
                Groups = new[] { "Structure" };
            else if (Comparer.Equals(category, "Cable Trays")) Groups = new[] { "Electrical" };
            else if (new[] { "Ducts", "Duct Terminals", "Air Terminals" }.Contains(category, Comparer))
                Groups = new[] { "HVAC" };
            else
            {
                var classes = (classification ?? "").Split(new[] { " / " }, StringSplitOptions.RemoveEmptyEntries);
                var groups = classes.Select(x => ClassGroups.TryGetValue(x.Trim(), out var group) ? group : "Unassigned/Other").ToArray();
                bool generic = classes.Length == 0 || classes.All(x => new[] { "UndefinedSystemType", "OtherPipe", "Global", "Fitting" }.Contains(x.Trim(), Comparer));
                if (generic)
                    groups = Systems.Select(x => TypeAliases.TryGetValue(x, out var group) ? group : "Unassigned/Other").ToArray();
                Groups = Distinct(groups);
                if (Groups.Length == 0) Groups = new[] { "Unassigned/Other" };
            }
        }

        internal static string[] Distinct(IEnumerable<string> values) => values.Select(x => x.Trim()).Distinct(Comparer).OrderBy(x => x, Comparer).ToArray();
        public bool HasSystem(string system) => Systems.Contains(system, Comparer);
        internal IEnumerable<string> Targets => Groups.Select(x => "group:" + x).Concat(Systems.Select(x => "system:" + x));
        internal bool MatchesTarget(string target) => string.IsNullOrEmpty(target) || Targets.Contains(target, Comparer);
    }

    public sealed class ClashCategoryInfo
    {
        private static readonly string[] GroupOrder = { "Structure", "Sanitary", "Water Supply", "Fire Protection", "HVAC", "Electrical", "Unassigned/Other" };
        public ClashSideCategories A { get; }
        public ClashSideCategories B { get; }
        public string[] Pairs { get; }
        public string PairLabel => string.Join(" / ", Pairs);
        public string[] Systems => ClashSideCategories.Distinct(A.Systems.Concat(B.Systems));

        public ClashCategoryInfo(ClashSideCategories a, ClashSideCategories b)
        {
            A = a; B = b;
            Pairs = ClashSideCategories.Distinct(from left in a.Groups from right in b.Groups
                select Array.IndexOf(GroupOrder, left) <= Array.IndexOf(GroupOrder, right)
                    ? left + " vs " + right : right + " vs " + left);
        }

        public bool Matches(string pair, string focus, string against)
        {
            if (!string.IsNullOrEmpty(pair) && !Pairs.Contains(pair, StringComparer.OrdinalIgnoreCase)) return false;
            if (string.IsNullOrEmpty(focus)) return true;
            // Against must match the opposite element, including when both elements have the focus system.
            return (A.HasSystem(focus) && B.MatchesTarget(against)) || (B.HasSystem(focus) && A.MatchesTarget(against));
        }

        public string[] Targets(string focus)
        {
            if (string.IsNullOrEmpty(focus)) return new string[0];
            return ClashSideCategories.Distinct((A.HasSystem(focus) ? B.Targets : Enumerable.Empty<string>())
                .Concat(B.HasSystem(focus) ? A.Targets : Enumerable.Empty<string>()));
        }
    }
}
