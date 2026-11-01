using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows.Controls;

namespace BIMEngine.Core.Dashboard
{
    // Minimal host for the production filter partial, so its WPF controls and event handlers
    // can run without Revit's native UI dependencies. No filter logic is duplicated here.
    public sealed class ClashRow
    {
        public string Type { get; set; }
        public ClashCategoryInfo Categories { get; set; }
    }

    public sealed partial class DashboardPage
    {
        private bool updating;
        private readonly ComboBox types = new ComboBox();
        private List<ClashRow> source = new List<ClashRow>(), visible;
        private static void AddFilter(Panel parent, string label, Control control, int width) => parent.Children.Add(control);
        private void Filter()
        {
            if (updating) return;
            updating = true;
            try { visible = FilterClashCategories(source.ToList()); }
            finally { updating = false; }
        }
        private void Choose(ComboBox combo, string key)
        {
            combo.SelectedItem = combo.Items.Cast<ClashFilterChoice>().Single(x => string.Equals(x.Key, key, StringComparison.OrdinalIgnoreCase));
        }
        private static ClashRow Row(string name, ClashSideCategories a, ClashSideCategories b) => new ClashRow { Type = name, Categories = new ClashCategoryInfo(a, b) };

        public static void RunFilterChecks()
        {
            int checks = 0;
            Action<bool, string> check = (condition, message) => { if (!condition) throw new Exception(message); checks++; };
            var page = new DashboardPage();
            page.AddClashFilters(new StackPanel());
            page.types.ItemsSource = new[] { "All Types" }; page.types.SelectedIndex = 0;
            page.updating = true; page.ResetClashFilters(); page.updating = false;
            page.updating = true; page.ResetClashFilters(); page.updating = false;
            check(page.coordinationPairs.SelectedIndex == 0 && page.focusSystems.SelectedIndex == 0 && page.againstSystems.SelectedIndex == 0, "Repeated clear on empty data still selects All");
            page.types.SelectionChanged += (s, e) => page.Filter();
            var beam = new ClashSideCategories("Structural Framing", null, null);
            var waste = new ClashSideCategories("Pipes", "PL-Waste", "Sanitary");
            var soil = new ClashSideCategories("Pipes", "PL-Soil", "Sanitary");
            var water = new ClashSideCategories("Pipes", "CW", "DomesticColdWater");
            var duct = new ClashSideCategories("Ducts", "Supply", "SupplyAir");
            var tray = new ClashSideCategories("Cable Trays", null, null);
            var multi = new ClashSideCategories("Pipes", "Multiple systems: PL-Waste / CW", "Sanitary / DomesticColdWater");
            var rows = new List<ClashRow> {
                Row("Beam / Waste", beam, waste), Row("Beam / Soil", beam, soil),
                Row("Duct / Waste", duct, waste), Row("Tray / Waste", tray, waste),
                Row("Waste / Waste", waste, waste), Row("Water / Duct", water, duct),
                Row("Beam / Multiple", beam, multi), Row("Beam / Waste", waste, beam)
            };
            page.source = rows; page.Filter();
            check(page.visible.Count == 8, "All rows remain visible initially");
            check(!page.againstSystems.IsEnabled, "Against disabled without a focus");
            check(page.coordinationPairs.Items.Cast<ClashFilterChoice>().Single(x => x.Key == "Structure vs Sanitary").Count == 4, "Coordination count is per row");
            check(page.focusSystems.Items.Cast<ClashFilterChoice>().Single(x => x.Key == "PL-Waste").Count == 6, "Both-sides focus count does not duplicate rows");
            var pairOptions = page.coordinationPairs.ItemsSource;
            page.Choose(page.coordinationPairs, "Structure vs Sanitary");
            check(ReferenceEquals(pairOptions, page.coordinationPairs.ItemsSource), "Selecting a pair preserves dropdown keyboard search state");
            check(page.visible.Count == 4, "Pair dropdown filters list");
            check(!page.types.Items.Contains("Duct / Waste"), "Detailed pairs cascade");
            page.types.SelectedItem = "Beam / Soil";
            check(page.visible.Count == 1, "Detailed pair narrows results");
            var systemOptions = page.focusSystems.ItemsSource;
            page.Choose(page.focusSystems, "PL-Waste");
            check(ReferenceEquals(systemOptions, page.focusSystems.ItemsSource), "Selecting a system preserves dropdown keyboard search state");
            check(page.visible.Count == 3 && page.types.SelectedIndex == 0, "Changing focus clears stale detailed pair");
            check(page.againstSystems.IsEnabled, "Against enabled with focus");
            check(page.againstSystems.Items.Cast<ClashFilterChoice>().Single(x => x.Key == "group:Structure").Count == 3, "Against counts opposite elements");
            page.Choose(page.coordinationPairs, null);
            check(page.visible.Count == 6, "Focus includes all opponent groups");
            page.Choose(page.againstSystems, "system:PL-Waste");
            check(page.visible.Count == 1 && page.visible[0].Type == "Waste / Waste", "Same-system match is one clash");
            page.Choose(page.againstSystems, "group:HVAC");
            check(page.visible.Count == 1 && page.visible[0].Type == "Duct / Waste", "Against group uses other side");
            page.Choose(page.focusSystems, "CW");
            check(Choice(page.againstSystems) == null && page.visible.Count == 2, "New focus resets opponent");
            page.source = new List<ClashRow>(); page.Filter();
            check(page.visible.Count == 0 && Choice(page.focusSystems) == "CW", "Empty refresh preserves focus");
            check(((ClashFilterChoice)page.focusSystems.SelectedItem).Count == 0, "Empty selection shows zero count");
            page.source = rows; page.Filter();
            check(page.visible.Count == 2, "Restored rows respect retained filter");
            page.updating = true; page.ResetClashFilters(); page.types.SelectedIndex = 0; page.updating = false; page.Filter();
            check(page.visible.Count == 8 && !page.againstSystems.IsEnabled, "Clear resets all classification filters");
            page.Choose(page.focusSystems, "PL-Waste");
            page.types.SelectedItem = "Beam / Waste";
            check(page.visible.Count == 2, "Detailed pair works within focus view");
            page.Choose(page.coordinationPairs, "Sanitary vs HVAC");
            check(page.visible.Count == 1 && page.types.SelectedIndex == 0, "Changing coordination pair resets detailed pair");
            check(page.focusSystems.IsTextSearchEnabled && TextSearch.GetTextPath(page.focusSystems) == "Label", "System type-to-select uses labels, not count suffixes");
            Console.WriteLine("PASS: " + checks + " WPF filter cascade and count checks.");
        }
    }
}
