using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Data;
using System.Windows.Media;

namespace BIMEngine.Core.Dashboard
{
    public sealed partial class DashboardPage
    {
        private readonly ComboBox grouping = new ComboBox(), sorting = new ComboBox();
        private readonly Dictionary<string, CheckBox> quickFilters = new Dictionary<string, CheckBox>();
        private readonly List<Button> triageButtons = new List<Button>();
        private readonly TextBlock selectionLabel = Text("Select a clash to triage", 11);
        private readonly TextBox triageText = new TextBox { MinWidth = 180, MaxLength = 4000, Margin = new Thickness(0, 4, 6, 4) };
        private StackPanel triageEditor;
        private string editorAction;
        private long? editorIssue;
        private Button bulkIgnore, saveTriage;

        private void AddListFilters(StackPanel header)
        {
            var chips = new WrapPanel { ToolTip = "Status chips combine. New and MEP vs Structure narrow the results. With no status selected, Open and Reviewed are shown." };
            foreach (var name in new[] { "New", "Open", "Reviewed", "Ignored", "Resolved", "MEP vs Structure" })
            {
                var chip = new CheckBox { Content = name, Foreground = Ink, Margin = new Thickness(6, 4, 6, 4) };
                chip.Click += (s, e) => Filter(); quickFilters.Add(name, chip);
                chips.Children.Add(new Border { Child = chip, Background = Panel, CornerRadius = new CornerRadius(10), Margin = new Thickness(0, 3, 5, 3) });
            }
            header.Children.Add(chips);
            var options = new WrapPanel();
            grouping.ItemsSource = new[] { "None (flat)", "Level", "Pair", "Status" }; grouping.SelectedIndex = 0;
            sorting.ItemsSource = new[] { "Most likely real", "Largest overlap", "Newest first", "Column sort" }; sorting.SelectedIndex = 0;
            sorting.ToolTip = "Most likely real: clashes with a named system first, then overlap size descending. A ranking aid, not a geometry verdict.";
            AddFilter(options, "GROUP BY", grouping, 145); AddFilter(options, "SORT", sorting, 175);
            grouping.SelectionChanged += (s, e) => Filter();
            sorting.SelectionChanged += (s, e) => { if (!updating) { foreach (var col in grid.Columns) col.SortDirection = null; Filter(); } };
            grid.Sorting += (s, e) => { updating = true; sorting.SelectedIndex = 3; updating = false; };
            header.Children.Add(options);
        }

        private bool MatchesQuickFilters(ClashRow row)
        {
            var statuses = new[] { "Open", "Reviewed", "Ignored", "Resolved" }.Where(x => quickFilters[x].IsChecked == true).ToArray();
            if (!(statuses.Length == 0 ? row.Status == "Open" || row.Status == "Reviewed" : statuses.Contains(row.Status))) return false;
            return (quickFilters["New"].IsChecked != true || row.Age == "New") &&
                (quickFilters["MEP vs Structure"].IsChecked != true || row.IsMepStructure);
        }

        private void ApplyListLayout(ListCollectionView view, SortDescription[] previousSort)
        {
            string group = grouping.SelectedItem as string;
            if (group == "Level" || group == "Status" || group == "Pair") view.GroupDescriptions.Add(new PropertyGroupDescription(group == "Pair" ? "Type" : group));
            if (sorting.SelectedIndex == 3 && previousSort != null)
                foreach (var sort in previousSort) view.SortDescriptions.Add(sort);
            else
            {
                if (sorting.SelectedIndex == 0) view.SortDescriptions.Add(new SortDescription("KnownSystemRank", ListSortDirection.Descending));
                view.SortDescriptions.Add(new SortDescription(sorting.SelectedIndex == 2 ? "Id" : "VolumeScore", ListSortDirection.Descending));
                view.SortDescriptions.Add(new SortDescription("Id", ListSortDirection.Descending));
            }
        }

        private void ConfigureListColumns()
        {
            AddColumn("Issue", "Id", 55);
            AddBadgeColumn("Status", "Status", "StatusBrush", 90);
            AddElementColumn("A"); AddElementColumn("B");
            AddColumn("Level", "Level", 85); AddColumn("Discipline pair", "DisciplinePair", 130);
            grid.Columns.Add(new DataGridTextColumn { Header = "Overlap size (mm)", Binding = new Binding("VolumeScore") { StringFormat = "{0:0.0}" }, SortMemberPath = "VolumeScore", Width = 130, MinWidth = 130 });
            AddBadgeColumn("Age", "Age", "AgeBrush", 80); AddColumn("Assigned to", "Assignee", 110);
            grid.ToolTip = "Ctrl+click or Shift+click to select multiple clashes. Bulk ignore is available for one pair type. Overlap is volume-derived, not penetration depth. Grey system icons mean Unassigned.";
        }

        private void AddBadgeColumn(string header, string path, string color, int width)
        {
            var border = new FrameworkElementFactory(typeof(Border));
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(8)); border.SetValue(Border.MarginProperty, new Thickness(3));
            border.SetValue(Border.PaddingProperty, new Thickness(5, 2, 5, 2)); border.SetValue(Border.BackgroundProperty, Navy);
            var text = new FrameworkElementFactory(typeof(TextBlock)); text.SetBinding(TextBlock.TextProperty, new Binding(path));
            text.SetBinding(TextBlock.ForegroundProperty, new Binding(color)); border.AppendChild(text);
            grid.Columns.Add(new DataGridTemplateColumn { Header = header, SortMemberPath = path, Width = width, MinWidth = width, CellTemplate = new DataTemplate { VisualTree = border } });
        }

        private void AddElementColumn(string side)
        {
            var panel = new FrameworkElementFactory(typeof(DockPanel));
            panel.SetBinding(FrameworkElement.ToolTipProperty, new Binding(side + ".Label"));
            var icon = new FrameworkElementFactory(typeof(TextBlock)); icon.SetBinding(TextBlock.TextProperty, new Binding(side + ".CategoryIcon"));
            icon.SetBinding(TextBlock.ForegroundProperty, new Binding(side + ".SystemBrush"));
            icon.SetValue(TextBlock.FontWeightProperty, FontWeights.Bold); icon.SetValue(FrameworkElement.WidthProperty, 22.0);
            icon.SetValue(FrameworkElement.MarginProperty, new Thickness(5, 5, 0, 0)); panel.AppendChild(icon);
            var text = new FrameworkElementFactory(typeof(TextBlock)); text.SetBinding(TextBlock.TextProperty, new Binding(side + ".ShortLabel"));
            text.SetValue(TextBlock.TextTrimmingProperty, TextTrimming.CharacterEllipsis);
            text.SetValue(FrameworkElement.MarginProperty, new Thickness(0, 5, 4, 0)); panel.AppendChild(text);
            grid.Columns.Add(new DataGridTemplateColumn { Header = side, Width = new DataGridLength(1, DataGridLengthUnitType.Star), MinWidth = 130, SortMemberPath = side + ".ShortLabel", CellTemplate = new DataTemplate { VisualTree = panel } });
        }

        private StackPanel CreateTriageBar()
        {
            var panel = new StackPanel(); panel.Children.Add(selectionLabel);
            var actions = new WrapPanel();
            foreach (var item in new[] { new[] { "Reviewed", "review" }, new[] { "Ignore", "ignore" }, new[] { "Add note", "note" }, new[] { "Assign", "assign" } })
            {
                string action = item[1];
                var button = Button(item[0], () => {
                    if (Selected == null) return;
                    if (action == "note" || action == "assign")
                    {
                        editorAction = action; editorIssue = Selected.Id; triageText.Text = "";
                        triageText.AcceptsReturn = action == "note"; triageText.Height = action == "note" ? 60 : 28;
                        triageText.ToolTip = action == "note" ? "Append a note" : "Assignee name (saved in Notes)";
                        saveTriage.Content = action == "note" ? "Save note" : "Save assignment";
                        triageEditor.Visibility = Visibility.Visible; UpdateTriageButtons(); triageText.Focus();
                    }
                    else DashboardController.RequestTriage(action, new[] { Selected.Id }, "");
                });
                triageButtons.Add(button); actions.Children.Add(button);
            }
            bulkIgnore = Button("Mark selected ignored", () => DashboardController.RequestTriage("ignore", grid.SelectedItems.Cast<ClashRow>().Select(x => x.Id).ToArray(), ""));
            bulkIgnore.ToolTip = "Select two or more clashes of the same pair type (Ctrl/Shift+click). Only selected rows are changed.";
            actions.Children.Add(bulkIgnore); panel.Children.Add(actions);
            triageEditor = new StackPanel { Visibility = Visibility.Collapsed };
            triageEditor.Children.Add(triageText);
            var editorButtons = new WrapPanel();
            saveTriage = Button("Save note", () => {
                if (!editorIssue.HasValue || string.IsNullOrWhiteSpace(triageText.Text)) { message.Text = "Enter text before saving."; return; }
                DashboardController.RequestTriage(editorAction, new[] { editorIssue.Value }, triageText.Text);
            });
            editorButtons.Children.Add(saveTriage); editorButtons.Children.Add(Button("Cancel edit", TriageSaved));
            triageEditor.Children.Add(editorButtons); panel.Children.Add(triageEditor); return panel;
        }

        private void UpdateTriageSelection()
        {
            if (editorIssue.HasValue && editorIssue != Selected?.Id) TriageSaved();
            int n = grid.SelectedItems.Count;
            selectionLabel.Text = n == 0 ? "Select a clash to triage" : n == 1 ? "TRIAGE · Issue #" + Selected?.Id : n + " selected · bulk ignore requires one pair type";
        }

        private void UpdateTriageButtons()
        {
            foreach (var button in triageButtons) button.IsEnabled = !busy && grid.SelectedItems.Count == 1;
            if (bulkIgnore != null) bulkIgnore.IsEnabled = !busy && grid.SelectedItems.Count > 1 && grid.SelectedItems.Cast<ClashRow>().Select(x => x.Type).Distinct().Count() == 1;
            if (saveTriage != null) saveTriage.IsEnabled = !busy && editorIssue.HasValue && editorIssue == Selected?.Id;
            triageText.IsEnabled = !busy;
        }

        public void TriageSaved()
        {
            editorIssue = null; editorAction = null; triageText.Text = "";
            if (triageEditor != null) triageEditor.Visibility = Visibility.Collapsed;
        }
    }
}
