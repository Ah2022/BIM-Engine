using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;

namespace BIMEngine.Core.Dashboard
{
    public sealed partial class DashboardPage
    {
        private readonly ComboBox coordinationPairs = new ComboBox(), focusSystems = new ComboBox(), againstSystems = new ComboBox();

        private sealed class ClashFilterChoice
        {
            public string Key { get; set; }
            public string Label { get; set; }
            public int Count { get; set; }
            public string Display => Label + " (" + Count + ")";
        }

        private void AddClashFilters(StackPanel header)
        {
            var filters = new WrapPanel { Margin = new Thickness(0, 10, 0, 0) };
            AddFilter(filters, "COORDINATION PAIR", coordinationPairs, 235);
            AddFilter(filters, "FOCUS SYSTEM", focusSystems, 210);
            AddFilter(filters, "AGAINST", againstSystems, 235);
            foreach (var combo in new[] { coordinationPairs, focusSystems, againstSystems })
            {
                combo.DisplayMemberPath = "Display";
                combo.IsTextSearchEnabled = true;
                TextSearch.SetTextPath(combo, "Label");
            }
            coordinationPairs.ToolTip = "Group clashes by discipline and system classification. Counts respect level, status and search.";
            focusSystems.ToolTip = "Type a system name to select it. Matches either element. Counts respect the coordination pair, level, status and search.";
            againstSystems.ToolTip = "Choose a group or exact system on the OTHER element. Counts respect the focus system and coordination pair.";
            coordinationPairs.SelectionChanged += (s, e) => {
                if (updating) return;
                updating = true; types.SelectedIndex = 0; updating = false; Filter();
            };
            focusSystems.SelectionChanged += (s, e) => {
                if (updating) return;
                updating = true; againstSystems.SelectedIndex = 0; types.SelectedIndex = 0; updating = false; Filter();
            };
            againstSystems.SelectionChanged += (s, e) => {
                if (updating) return;
                updating = true; types.SelectedIndex = 0; updating = false; Filter();
            };
            header.Children.Add(filters);
        }

        private static string Choice(ComboBox combo) => (combo.SelectedItem as ClashFilterChoice)?.Key;
        private static string ChoiceLabel(string key)
        {
            if (key.StartsWith("group:", StringComparison.Ordinal)) return "Group: " + key.Substring(6);
            if (key.StartsWith("system:", StringComparison.Ordinal)) return "System: " + key.Substring(7);
            return key;
        }

        private static void FillChoices(ComboBox combo, string all, IEnumerable<IEnumerable<string>> rowKeys)
        {
            string selected = Choice(combo);
            var keys = rowKeys.Select(x => x.Distinct(StringComparer.OrdinalIgnoreCase).ToArray()).ToList();
            var choices = keys.SelectMany(x => x).GroupBy(x => x, StringComparer.OrdinalIgnoreCase)
                .Select(x => new ClashFilterChoice { Key = x.Key, Label = ChoiceLabel(x.Key), Count = x.Count() })
                .OrderBy(x => x.Label, StringComparer.OrdinalIgnoreCase).ToList();
            // Keep a now-empty selection visible instead of silently widening a user's filter.
            if (!string.IsNullOrEmpty(selected) && !choices.Any(x => string.Equals(x.Key, selected, StringComparison.OrdinalIgnoreCase)))
                choices.Add(new ClashFilterChoice { Key = selected, Label = ChoiceLabel(selected), Count = 0 });
            choices.Insert(0, new ClashFilterChoice { Label = all, Count = keys.Count });
            var previous = combo.Items.Cast<ClashFilterChoice>().ToArray();
            // Keep the active dropdown and WPF's incremental keyboard search intact when only
            // a downstream filter changed; replacing ItemsSource resets that interaction.
            if (previous.Length == choices.Count && previous.Zip(choices, (a, b) => a.Key == b.Key && a.Label == b.Label && a.Count == b.Count).All(x => x))
            {
                if (combo.SelectedIndex < 0) combo.SelectedIndex = 0;
                return;
            }
            combo.ItemsSource = choices;
            combo.SelectedItem = choices.FirstOrDefault(x => string.Equals(x.Key, selected, StringComparison.OrdinalIgnoreCase)) ?? choices[0];
        }

        private void ResetClashFilters()
        {
            coordinationPairs.SelectedIndex = focusSystems.SelectedIndex = againstSystems.SelectedIndex = -1;
            var empty = Enumerable.Empty<IEnumerable<string>>();
            FillChoices(coordinationPairs, "All coordination pairs", empty);
            FillChoices(focusSystems, "All systems", empty);
            FillChoices(againstSystems, "All", empty);
            againstSystems.IsEnabled = false;
        }

        // Called under the updating guard: each next dropdown is scoped by the controls before it.
        private List<ClashRow> FilterClashCategories(List<ClashRow> rows)
        {
            FillChoices(coordinationPairs, "All coordination pairs", rows.Select(x => x.Categories.Pairs));
            string pair = Choice(coordinationPairs);
            rows = rows.Where(x => x.Categories.Matches(pair, null, null)).ToList();
            FillChoices(focusSystems, "All systems", rows.Select(x => x.Categories.Systems));
            string focus = Choice(focusSystems);
            rows = rows.Where(x => x.Categories.Matches(null, focus, null)).ToList();
            againstSystems.IsEnabled = !string.IsNullOrEmpty(focus);
            if (!againstSystems.IsEnabled) againstSystems.SelectedIndex = 0;
            FillChoices(againstSystems, "All", rows.Select(x => x.Categories.Targets(focus)));
            rows = rows.Where(x => x.Categories.Matches(null, focus, Choice(againstSystems))).ToList();
            string detail = types.SelectedIndex <= 0 ? null : types.SelectedItem as string;
            var details = rows.Select(x => x.Type).Distinct().OrderBy(x => x).ToList();
            if (detail != null && !details.Contains(detail)) details.Add(detail);
            var detailItems = new[] { "All Types" }.Concat(details).ToArray();
            if (!types.Items.Cast<string>().SequenceEqual(detailItems)) types.ItemsSource = detailItems;
            types.SelectedItem = detail ?? "All Types";
            return rows.Where(x => detail == null || x.Type == detail).ToList();
        }
    }
}
