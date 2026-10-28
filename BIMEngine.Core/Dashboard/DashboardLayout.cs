using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;

namespace BIMEngine.Core.Dashboard
{
    public sealed partial class DashboardPage
    {
        // Device-independent pixels: leave room for the grid and a readable review pane.
        internal const double ReviewBreakpoint = 1040;
        private Grid layoutRoot, listPane, reviewPane;
        private GridSplitter reviewSplitter;
        private ScrollViewer listControls, reviewControls;
        private bool? sideBySide;
        private readonly TextBlock reviewA = Text("Select a clash", 14), reviewB = Text("", 14),
            reviewLevel = Text("", 12), reviewSystem = Text("", 12), reviewMeta = Text("", 11), reviewExtra = Text("", 12), reviewPosition = Text("No clashes", 11);
        private Border reviewCard;
        private Button previousClash, nextClash, copyIds;
        public bool IsSideBySide => sideBySide == true;

        private void ConfigureResponsiveLayout(Grid root, StackPanel header, StackPanel inspector, WrapPanel previewTools)
        {
            layoutRoot = root;
            listPane = new Grid(); reviewPane = new Grid();
            listPane.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            listPane.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            listControls = new ScrollViewer { Content = header, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
            listPane.Children.Add(listControls); Grid.SetRow(grid, 1); listPane.Children.Add(grid);
            reviewPane.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            reviewPane.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            reviewPane.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            reviewPane.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            var reviewFlow = CreateReviewNavigation(); reviewPane.Children.Add(reviewFlow);
            reviewControls = new ScrollViewer { Content = inspector, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
            Grid.SetRow(reviewControls, 1); reviewPane.Children.Add(reviewControls); Grid.SetRow(preview, 2); reviewPane.Children.Add(preview);
            Grid.SetRow(previewTools, 3); reviewPane.Children.Add(previewTools);
            reviewSplitter = new GridSplitter { Background = Teal, ResizeBehavior = GridResizeBehavior.PreviousAndNext };
            root.Children.Add(listPane); root.Children.Add(reviewSplitter); root.Children.Add(reviewPane); root.Children.Add(message);
            listPane.SizeChanged += (s, e) => listControls.MaxHeight = Math.Max(0, listPane.ActualHeight * .55);
            Action sizeReview = () => reviewControls.MaxHeight = Math.Max(0, (reviewPane.ActualHeight - reviewFlow.ActualHeight - previewTools.ActualHeight) * .60);
            reviewPane.SizeChanged += (s, e) => sizeReview(); reviewFlow.SizeChanged += (s, e) => sizeReview(); previewTools.SizeChanged += (s, e) => sizeReview();
            root.SizeChanged += (s, e) => UpdateResponsiveLayout();
            root.Loaded += (s, e) => UpdateResponsiveLayout();
            grid.Resources[SystemColors.HighlightBrushKey] = DashboardTheme.Selection;
            grid.Resources[SystemColors.HighlightTextBrushKey] = Ink;
            grid.Resources[SystemColors.InactiveSelectionHighlightBrushKey] = DashboardTheme.Selection;
            grid.Resources[SystemColors.InactiveSelectionHighlightTextBrushKey] = Ink;
            triageText.Background = Panel; triageText.Foreground = Ink; triageText.BorderBrush = Muted;
            UpdateResponsiveLayout();
        }

        [DllImport("user32.dll")]
        private static extern IntPtr GetAncestor(IntPtr window, uint flags);

        private bool IsFloatingHost()
        {
            if (floatingWindow != null) return true;
            // Revit's native floating frame is a separate top-level HWND. No model/API calls on resize.
            var source = PresentationSource.FromVisual(dashboardRoot) as HwndSource;
            return OwnerHandle != IntPtr.Zero && source != null && GetAncestor(source.Handle, 2) != OwnerHandle;
        }

        private void UpdateResponsiveLayout()
        {
            if (layoutRoot == null) return;
            bool wide = IsFloatingHost() && layoutRoot.ActualWidth >= ReviewBreakpoint;
            if (sideBySide == wide) return;
            sideBySide = wide;
            layoutRoot.ColumnDefinitions.Clear(); layoutRoot.RowDefinitions.Clear();
            if (wide)
            {
                layoutRoot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1.15, GridUnitType.Star) });
                layoutRoot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(8) });
                layoutRoot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                layoutRoot.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
                layoutRoot.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                Grid.SetRow(listPane, 0); Grid.SetColumn(listPane, 0);
                Grid.SetRow(reviewSplitter, 0); Grid.SetColumn(reviewSplitter, 1);
                Grid.SetRow(reviewPane, 0); Grid.SetColumn(reviewPane, 2);
                Grid.SetRow(message, 1); Grid.SetColumnSpan(message, 3);
                reviewSplitter.ResizeDirection = GridResizeDirection.Columns;
                reviewSplitter.Width = 5; reviewSplitter.Height = double.NaN;
                reviewSplitter.HorizontalAlignment = HorizontalAlignment.Center; reviewSplitter.VerticalAlignment = VerticalAlignment.Stretch;
            }
            else
            {
                layoutRoot.ColumnDefinitions.Add(new ColumnDefinition());
                layoutRoot.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
                layoutRoot.RowDefinitions.Add(new RowDefinition { Height = new GridLength(8) });
                layoutRoot.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1.2, GridUnitType.Star) });
                layoutRoot.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                Grid.SetRow(listPane, 0); Grid.SetColumn(listPane, 0);
                Grid.SetRow(reviewSplitter, 1); Grid.SetColumn(reviewSplitter, 0);
                Grid.SetRow(reviewPane, 2); Grid.SetColumn(reviewPane, 0);
                Grid.SetRow(message, 3); Grid.SetColumnSpan(message, 1);
                reviewSplitter.ResizeDirection = GridResizeDirection.Rows;
                reviewSplitter.Height = 5; reviewSplitter.Width = double.NaN;
                reviewSplitter.HorizontalAlignment = HorizontalAlignment.Stretch; reviewSplitter.VerticalAlignment = VerticalAlignment.Center;
            }
        }

        private Border CreateReviewCard()
        {
            var content = new StackPanel();
            var heading = new DockPanel();
            copyIds = Button("⧉", () => CopyIds("both"));
            copyIds.ToolTip = "Copy IDs for A and B"; AutomationProperties.SetName(copyIds, "Copy IDs");
            DockPanel.SetDock(copyIds, Dock.Right); heading.Children.Add(copyIds);
            var label = Text("Now reviewing", 16); label.FontWeight = FontWeights.SemiBold; heading.Children.Add(label);
            content.Children.Add(heading); content.Children.Add(reviewMeta);
            var pair = new Grid { Margin = new Thickness(0, 8, 0, 8) };
            pair.ColumnDefinitions.Add(new ColumnDefinition()); pair.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto }); pair.ColumnDefinitions.Add(new ColumnDefinition());
            pair.Children.Add(reviewA);
            var vs = Text("vs", 11); vs.Margin = new Thickness(10, 3, 10, 0); vs.Foreground = Muted;
            Grid.SetColumn(vs, 1); pair.Children.Add(vs); Grid.SetColumn(reviewB, 2); pair.Children.Add(reviewB);
            content.Children.Add(pair);
            content.Children.Add(reviewLevel); reviewSystem.Margin = new Thickness(0, 6, 0, 6); content.Children.Add(reviewSystem);
            var extra = new Expander { Header = "More details", Foreground = Ink, Content = reviewExtra }; content.Children.Add(extra);
            reviewCard = new Border { Child = content, Background = Panel, BorderBrush = Muted, BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(6), Padding = new Thickness(10) };
            return reviewCard;
        }

        private void UpdateReviewCard(ClashRow row)
        {
            reviewA.Text = row == null ? "Select a clash" : "A  " + row.A.ShortLabel;
            reviewB.Text = row == null ? "" : "B  " + row.B.ShortLabel;
            reviewA.Foreground = row?.A.SystemBrush ?? Ink; reviewB.Foreground = row?.B.SystemBrush ?? Ink;
            reviewMeta.Text = row == null ? "Choose a row or use Next to begin." : "Issue #" + row.Id + " · " + row.Status + " · " + row.Age + string.Format(" · Overlap size {0:0.0} mm", row.VolumeScore);
            reviewLevel.Text = row == null ? "" : "Level · " + row.Level;
            reviewSystem.Text = row == null ? "" : "System A · " + row.A.SystemType + " · " + row.A.SystemName + "\nSystem B · " + row.B.SystemType + " · " + row.B.SystemName;
            reviewExtra.Text = row == null ? "" : "A · " + row.A.Label + "\nB · " + row.B.Label + "\nClassification · " + row.Classification +
                "\nSystem classification A · " + row.A.SystemClassification + "\nSystem classification B · " + row.B.SystemClassification +
                "\nFamily A · " + row.A.FamilyType + "\nFamily B · " + row.B.FamilyType + "\n" + row.Notes;
            reviewCard.ToolTip = row == null ? null : string.Format("XYZ (internal ft): {0:0.###}, {1:0.###}, {2:0.###}\nA link: {3}\nB link: {4}\nOverlap size is volume-derived, not penetration depth.", row.X, row.Y, row.Z, row.A.LinkId, row.B.LinkId);
        }

        private WrapPanel CreateReviewNavigation()
        {
            var panel = new WrapPanel();
            previousClash = Button("← Previous", () => MoveReview(-1)); nextClash = Button("Next →", () => MoveReview(1));
            AutomationProperties.SetName(previousClash, "Previous clash"); AutomationProperties.SetName(nextClash, "Next clash");
            panel.Children.Add(previousClash); panel.Children.Add(nextClash);
            reviewPosition.Margin = new Thickness(5, 12, 0, 0); panel.Children.Add(reviewPosition); return panel;
        }

        private void MoveReview(int direction)
        {
            int index = grid.Items.IndexOf(Selected);
            int target = index < 0 ? (direction > 0 ? 0 : grid.Items.Count - 1) : index + direction;
            if (target < 0 || target >= grid.Items.Count) return;
            var row = (ClashRow)grid.Items[target];
            grid.SelectedItems.Clear(); grid.SelectedItem = row; grid.CurrentItem = row; grid.ScrollIntoView(row);
        }

        private void UpdateReviewNavigation()
        {
            int index = grid.Items.IndexOf(Selected), total = grid.Items.Count;
            if (previousClash != null) previousClash.IsEnabled = !busy && total > 0 && index != 0;
            if (nextClash != null) nextClash.IsEnabled = !busy && total > 0 && index < total - 1;
            if (copyIds != null) copyIds.IsEnabled = Selected != null;
            reviewPosition.Text = total == 0 ? "No clashes" : index < 0 ? total + " clashes" : (index + 1) + " of " + total;
        }
    }
}
