using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using System.Web.Script.Serialization;
using Autodesk.Revit.UI;
using ComboBox = System.Windows.Controls.ComboBox;
using TextBox = System.Windows.Controls.TextBox;

namespace BIMEngine.Core.Dashboard
{
    public sealed partial class DashboardPage : Page, IDockablePaneProvider
    {
        internal static readonly Brush Navy = DashboardTheme.Background, Panel = DashboardTheme.Surface,
            Teal = DashboardTheme.Accent, Ink = DashboardTheme.Text, Muted = DashboardTheme.Secondary;
        private readonly ComboBox levels = new ComboBox(), types = new ComboBox();
        private readonly TextBox search = new TextBox();
        private readonly TextBlock title = Text("CLASH DASHBOARD", 19), summary = Text("", 11), count = Text("", 12),
            message = Text("Ready", 11);
        private readonly DataGrid grid = new DataGrid();
        private readonly InspectionViewport preview = new InspectionViewport();
        private readonly TextBlock previewTitle = Text("Select a clash for a 3D preview", 10);
        private readonly Dictionary<string, CheckBox> categories = new Dictionary<string, CheckBox>();
        private readonly CheckBox includeLinks = new CheckBox { Content = "Include links", Foreground = Ink, IsChecked = true, Margin = new Thickness(0, 8, 12, 8) };
        private readonly ProgressBar scanProgress = new ProgressBar { Height = 4, Minimum = 0, Maximum = 100, Visibility = Visibility.Collapsed };
        private readonly TextBlock scanStatus = Text("Choose scope, then scan", 11), rawSummary = Text("", 11);
        private readonly Expander scanDetails = new Expander { Header = "Details", Foreground = Ink };
        private readonly Dictionary<string, RadioButton> viewTabs = new Dictionary<string, RadioButton>();
        private readonly DispatcherTimer selectionTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(180) };
        private bool previewPending;
        private StackPanel scanPanel;
        private long? previewIssue;
        private readonly List<Button> buttons = new List<Button>();
        private readonly Slider context = new Slider { Minimum = 1, Maximum = 10, Value = 2, Width = 110, TickFrequency = 1, IsSnapToTickEnabled = true };
        private DashboardSnapshot snapshot;
        private bool updating, busy;
        private FrameworkElement dashboardRoot;
        private Window floatingWindow;
        private Button undockButton;
        internal IntPtr OwnerHandle { get; set; }
        public ClashRow Selected => grid.CurrentItem is ClashRow current && grid.SelectedItems.Contains(current) ? current : grid.SelectedItem as ClashRow;
        public double ContextFeet => context.Value / .3048;
        public int VisibleCount => grid.Items.Count;
        public string Message => message.Text;
        public string ScanScopeJson => new JavaScriptSerializer().Serialize(new {
            Categories = categories.Where(x => x.Value.IsChecked == true).Select(x => x.Key).ToArray(),
            IncludeLinkedDocuments = includeLinks.IsChecked == true });

        public DashboardPage()
        {
            Background = Navy; Foreground = Ink;
            FontFamily = new FontFamily("Segoe UI"); FontSize = 13;
            var root = new Grid { Margin = new Thickness(12), Background = Navy };
            dashboardRoot = root;
            var header = new StackPanel();
            header.Children.Add(title);
            header.Children.Add(Text("MODEL COORDINATION  /  HARD CLASHES", 10));
            scanPanel = new StackPanel { Margin = new Thickness(0, 8, 0, 4) };
            scanPanel.Children.Add(Text("SCAN", 12));
            var chips = new WrapPanel();
            foreach (var name in new[] { "Pipes", "Ducts", "Cable Trays", "Structural Framing", "Structural Columns", "Duct Terminals", "Air Terminals", "Pipe Accessories" })
            {
                var chip = new CheckBox { Content = name, Foreground = Ink, Margin = new Thickness(6), IsChecked = categories.Count < 5 };
                categories.Add(name, chip);
                chips.Children.Add(new Border { Child = chip, Background = Panel, BorderBrush = Teal, BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(10), Margin = new Thickness(0, 3, 5, 3) });
            }
            scanPanel.Children.Add(chips);
            var scanActions = new WrapPanel();
            scanActions.Children.Add(includeLinks);
            scanActions.Children.Add(Button("Scan", () => {
                if (!categories.Any(x => x.Value.IsChecked == true)) { scanStatus.Text = "Choose at least one category."; return; }
                DashboardController.Request("refresh");
            }));
            scanActions.Children.Add(scanStatus); scanPanel.Children.Add(scanActions);
            scanPanel.Children.Add(scanProgress); header.Children.Add(scanPanel);
            AddClashFilters(header);
            var filters = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
            AddFilter(filters, "LEVEL", levels, 155); AddFilter(filters, "DETAILED PAIR", types, 210);
            AddFilter(filters, "SEARCH", search, 180);
            header.Children.Add(filters);
            AddListFilters(header);
            var actions = new WrapPanel();
            undockButton = Button("Undock", ToggleFloating);
            actions.Children.Add(undockButton);
            actions.Children.Add(Button("Clear Filters", () => { updating = true; ResetClashFilters(); levels.SelectedIndex = types.SelectedIndex = 0; search.Text = ""; foreach (var chip in quickFilters.Values) chip.IsChecked = false; updating = false; Filter(); }));
            actions.Children.Add(Button("Delete generated views", () => DashboardController.Request("cleanup")));
            header.Children.Add(actions);
            summary.Foreground = Teal; summary.TextWrapping = TextWrapping.NoWrap; summary.TextTrimming = TextTrimming.CharacterEllipsis;
            header.Children.Add(summary);
            scanDetails.Content = new ScrollViewer { Content = rawSummary, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, MaxHeight = 100 };
            header.Children.Add(scanDetails);
            count.Margin = new Thickness(0, 8, 0, 8); count.Foreground = Teal; header.Children.Add(count);


            grid.AutoGenerateColumns = false; grid.IsReadOnly = true;
            grid.CanUserAddRows = grid.CanUserDeleteRows = false;
            grid.SelectionMode = DataGridSelectionMode.Extended; grid.SelectionUnit = DataGridSelectionUnit.FullRow;
            grid.Background = Panel; grid.Foreground = Ink; grid.RowBackground = Panel;
            grid.AlternatingRowBackground = DashboardTheme.Alternate; grid.BorderThickness = new Thickness(0);
            grid.GridLinesVisibility = DataGridGridLinesVisibility.None;
            grid.RowHeaderWidth = 0; grid.MinRowHeight = 32;
            grid.EnableRowVirtualization = true;
            VirtualizingPanel.SetIsVirtualizingWhenGrouping(grid, true);
            VirtualizingPanel.SetVirtualizationMode(grid, VirtualizationMode.Recycling);
            var hs = new Style(typeof(DataGridColumnHeader));
            hs.Setters.Add(new Setter(Control.BackgroundProperty, Navy));
            hs.Setters.Add(new Setter(Control.ForegroundProperty, Muted));
            hs.Setters.Add(new Setter(Control.PaddingProperty, new Thickness(7)));
            grid.ColumnHeaderStyle = hs;
            ConfigureListColumns();
            var group = new GroupStyle();
            var groupText = new FrameworkElementFactory(typeof(TextBlock));
            groupText.SetBinding(TextBlock.TextProperty, new Binding("Name"));
            groupText.SetValue(TextBlock.ForegroundProperty, Teal);
            groupText.SetValue(TextBlock.FontWeightProperty, FontWeights.SemiBold);
            groupText.SetValue(FrameworkElement.MarginProperty, new Thickness(5, 7, 0, 7));
            var expander = new FrameworkElementFactory(typeof(Expander));
            expander.SetValue(Expander.IsExpandedProperty, true);
            expander.SetValue(Control.ForegroundProperty, Ink);
            expander.SetValue(HeaderedContentControl.HeaderTemplateProperty, new DataTemplate { VisualTree = groupText });
            expander.SetBinding(HeaderedContentControl.HeaderProperty, new Binding());
            expander.AppendChild(new FrameworkElementFactory(typeof(ItemsPresenter)));
            var gs = new Style(typeof(GroupItem));
            gs.Setters.Add(new Setter(Control.TemplateProperty, new ControlTemplate(typeof(GroupItem)) { VisualTree = expander }));
            group.ContainerStyle = gs;
            grid.GroupStyle.Add(group);
            var inspector = new StackPanel();
            inspector.Children.Add(CreateReviewCard());
            var navigation = new WrapPanel();
            navigation.Children.Add(Button("Select in Revit", () => DashboardController.Request("select")));
            navigation.Children.Add(Button("Pin as view", () => DashboardController.Request("pin")));
            navigation.Children.Add(Button("End Preview", () => { previewPending = false; selectionTimer.Stop(); DashboardController.Request("end"); }));
            var advanced = new StackPanel { Background = Panel, Margin = new Thickness(8) };
            var tools = new WrapPanel();
            tools.Children.Add(Button("Rotate 90°", () => DashboardController.Request("rotate")));
            advanced.Children.Add(tools);
            var options = new WrapPanel();
            var showContext = new CheckBox { Content="Nearby context",IsChecked=true,Foreground=Ink,Margin=new Thickness(0,4,12,4) };
            showContext.Click+=(s,e)=>{InspectionSession.ShowContext=showContext.IsChecked==true;InspectionSession.Present();};
            var focus = new CheckBox { Content="Focus clash",Foreground=Ink,Margin=new Thickness(0,4,12,4) };
            focus.Click+=(s,e)=>{InspectionSession.FocusClash=focus.IsChecked==true;InspectionSession.Present();};
            options.Children.Add(showContext);options.Children.Add(focus);
            options.Children.Add(Button("Section axis A / B", () => {InspectionSession.UseB=!InspectionSession.UseB;InspectionSession.Present();}));
            advanced.Children.Add(options);
            var settings = new WrapPanel(); settings.Children.Add(Text("Context (m)", 11)); settings.Children.Add(context);
            var contextValue = Text("", 11); contextValue.SetBinding(TextBlock.TextProperty, new Binding("Value") { Source = context, StringFormat = "{0:0} m" });
            settings.Children.Add(contextValue); advanced.Children.Add(settings);
            context.ValueChanged+=(s,e)=>{InspectionSession.Padding=ContextFeet;InspectionSession.Present();};
            previewTitle.Margin = new Thickness(0, 8, 0, 6);
            var viewportHeader = new StackPanel();
            viewportHeader.Children.Add(CreateTriageBar());
            viewportHeader.Children.Add(navigation);
            var tabs = new WrapPanel();
            foreach (var mode in new[] { "3d", "2d", "section" })
            {
                string selectedMode = mode;
                var tab = new RadioButton { Content = mode == "section" ? "Section" : mode.ToUpperInvariant(), GroupName = "PreviewMode", Foreground = Ink,
                    Padding = new Thickness(12, 6, 12, 6), Margin = new Thickness(0, 3, 8, 3), IsChecked = mode == "3d" };
                var tabBorder = new FrameworkElementFactory(typeof(Border));
                tabBorder.SetValue(Border.BorderThicknessProperty, new Thickness(0, 0, 0, 2));
                tabBorder.SetBinding(Border.BorderBrushProperty, new Binding("Background") { RelativeSource = new RelativeSource(RelativeSourceMode.TemplatedParent) });
                tabBorder.SetValue(Border.PaddingProperty, new Thickness(12, 6, 12, 6));
                tabBorder.AppendChild(new FrameworkElementFactory(typeof(ContentPresenter)));
                var tabStyle = new Style(typeof(RadioButton));
                tabStyle.Setters.Add(new Setter(Control.BackgroundProperty, Muted));
                tabStyle.Setters.Add(new Setter(Control.TemplateProperty, new ControlTemplate(typeof(RadioButton)) { VisualTree = tabBorder }));
                var selectedTab = new Trigger { Property = System.Windows.Controls.Primitives.ToggleButton.IsCheckedProperty, Value = true };
                selectedTab.Setters.Add(new Setter(Control.BackgroundProperty, Teal));
                selectedTab.Setters.Add(new Setter(Control.ForegroundProperty, Teal));
                tabStyle.Triggers.Add(selectedTab); tab.Style = tabStyle;
                tab.Click += (s, e) => { previewPending = false; selectionTimer.Stop(); DashboardController.Request(selectedMode); };
                viewTabs.Add(mode, tab); tabs.Children.Add(tab);
            }
            var gear = Button("⚙", () => { }); gear.ToolTip = "Preview options";
            var popup = new Popup { PlacementTarget = gear, Placement = PlacementMode.Bottom, StaysOpen = false,
                Child = new Border { Child = advanced, Background = Panel, BorderBrush = Teal, BorderThickness = new Thickness(1) } };
            gear.Click += (s, e) => popup.IsOpen = !popup.IsOpen;
            tabs.Children.Add(gear); tabs.Children.Add(popup);
            viewportHeader.Children.Add(tabs); viewportHeader.Children.Add(previewTitle);
            inspector.Children.Add(viewportHeader);
            var previewTools = new WrapPanel();
            previewTools.Children.Add(Button("Fit Preview", preview.Fit));
            previewTools.Children.Add(Text("Wheel: zoom · Drag: pan · A teal / B orange / overlap red", 10));
            ConfigureResponsiveLayout(root, header, inspector, previewTools);
            message.Foreground = Muted; message.Margin = new Thickness(0, 8, 0, 0);

            Content = dashboardRoot;
            levels.SelectionChanged += (s, e) => Filter(); types.SelectionChanged += (s, e) => Filter();
            search.TextChanged += (s, e) => Filter();
            grid.SelectionChanged += (s, e) => Inspect();
            grid.CurrentCellChanged += (s, e) => { if (!updating) Inspect(); };
            dashboardRoot.PreviewKeyDown += OnKeyDown;
            selectionTimer.Tick += (s, e) => {
                if (!ReferenceEquals(DashboardController.Page, this)) { selectionTimer.Stop(); return; }
                if (DashboardController.Busy) return;
                selectionTimer.Stop();
                if (previewPending && Selected != null) { previewPending = false; DashboardController.Request("3d"); }
            };
            Clear("Open and save a project, then press Scan.");
        }

        public void SetupDockablePane(DockablePaneProviderData data)
        {
            data.FrameworkElement = this;
            data.InitialState = new DockablePaneState { DockPosition = DockPosition.Right, MinimumWidth = 380, MinimumHeight = 500 };
            data.VisibleByDefault = false;
        }
        internal static Brush BrushOf(byte r, byte g, byte b) => new SolidColorBrush(Color.FromRgb(r, g, b));
        private void CopyIds(string which)
        {
            if (Selected == null) return;
            string value = which == "A" ? Selected.A.ElementId.ToString() : which == "B" ? Selected.B.ElementId.ToString() : Selected.A.ElementId + ", " + Selected.B.ElementId;
            try { Clipboard.SetText(value); message.Text = "Copied element ID" + (which == "both" ? "s: " : ": ") + value; }
            catch (System.Runtime.InteropServices.ExternalException) { message.Text = "Clipboard is busy. Try Copy again, or select the ID and press Ctrl+C."; }
        }
        private void ToggleFloating()
        {
            if (floatingWindow != null) { floatingWindow.Close(); return; }
            var area = SystemParameters.WorkArea;
            var window = new Window { Title = "BIM Engine · Clashes", Background = Navy,
                FontFamily = FontFamily, FontSize = FontSize, Foreground = Ink,
                Width = Math.Min(1180, area.Width), Height = Math.Min(940, area.Height),
                MinWidth = Math.Min(420, area.Width), MinHeight = Math.Min(420, area.Height),
                Left = area.Left + Math.Max(0, (area.Width - 1180) / 2), Top = area.Top,
                ResizeMode = ResizeMode.CanResizeWithGrip, ShowInTaskbar = false };
            if (OwnerHandle != IntPtr.Zero) new System.Windows.Interop.WindowInteropHelper(window).Owner = OwnerHandle;
            Content = null; window.Content = dashboardRoot;
            floatingWindow = window; undockButton.Content = "Dock back"; UpdateResponsiveLayout();
            var placeholder = new StackPanel { Margin = new Thickness(16) };
            placeholder.Children.Add(Text("Dashboard is open in a floating window.", 14));
            var restore = new Button { Content = "Dock back", Margin = new Thickness(0, 12, 0, 0), Padding = new Thickness(10) };
            restore.Click += (s, e) => window.Close(); placeholder.Children.Add(restore); Content = placeholder;
            window.Closed += (s, e) => { window.Content = null; Content = dashboardRoot; floatingWindow = null; undockButton.Content = "Undock"; UpdateResponsiveLayout(); };
            window.Show();
        }
        internal void ActivateFloating()
        {
            if (floatingWindow == null) return;
            if (floatingWindow.WindowState == WindowState.Minimized) floatingWindow.WindowState = WindowState.Normal;
            floatingWindow.Activate();
        }
        internal static TextBlock Text(string value, double size) => new TextBlock { Text = value, FontSize = size, Foreground = Ink, TextWrapping = TextWrapping.Wrap };
        private Button Button(string label, Action action)
        {
            var button = new Button { Content = label, Padding = new Thickness(10, 6, 10, 6), Margin = new Thickness(0, 5, 6, 5),
                Background = Panel, Foreground = Ink, BorderBrush = Teal };
            button.Style = DashboardThemeControls.ButtonStyle;
            button.Click += (s, e) => action(); buttons.Add(button); return button;
        }
        private static void AddFilter(Panel parent, string label, Control control, int width)
        {
            var stack = new StackPanel { Width = width, Margin = new Thickness(0, 0, 6, 6) };
            stack.Children.Add(Text(label, 10)); control.Height = 28;
            control.Foreground = Ink; control.Background = Panel;
            if (control is ComboBox combo) combo.Style = DashboardThemeControls.ComboStyle;
            stack.Children.Add(control); parent.Children.Add(stack);
        }
        private void AddColumn(string name, string path, int width) => grid.Columns.Add(new DataGridTextColumn { Header = name, Binding = new Binding(path), Width = width, MinWidth = width });
        public void Clear(string text)
        {
            TriageSaved(); foreach (var chip in quickFilters.Values) chip.IsChecked = false;
            previewPending = false; selectionTimer.Stop(); rawSummary.Text = ""; scanDetails.IsExpanded = false;
            snapshot = null; grid.ItemsSource = null; title.Text = "CLASH DASHBOARD"; summary.Text = text;
            count.Text = "0 active clashes"; updating = true;
            ResetClashFilters();
            levels.ItemsSource = new[] { "All Levels" }; types.ItemsSource = new[] { "All Types" };
            levels.SelectedIndex = types.SelectedIndex = 0; search.Text = ""; updating = false; Inspect();
        }
        public void Display(DashboardSnapshot value)
        {
            bool same = snapshot?.Project == value.Project;
            string level = same ? levels.SelectedItem as string : null, type = same ? types.SelectedItem as string : null;
            snapshot = value; title.Text = "CLASH DASHBOARD · " + value.Title; summary.Text = value.SummaryStrip ?? value.Summary;
            foreach (var row in value.Issues) row.RefreshCategories();
            summary.ToolTip = summary.Text; rawSummary.Text = value.Summary;
            if (!same && value.ScanConfig != null)
            {
                foreach (var pair in categories) pair.Value.IsChecked = value.ScanConfig.Categories.Contains(pair.Key);
                includeLinks.IsChecked = value.ScanConfig.IncludeLinkedDocuments;
            }
            updating = true;
            levels.ItemsSource = new[] { "All Levels" }.Concat(value.Issues.OrderBy(x => x.LevelId).Select(x => x.Level).Distinct()).ToArray();
            types.ItemsSource = new[] { "All Types" }.Concat(value.Issues.Select(x => x.Type).Distinct().OrderBy(x => x)).ToArray();
            levels.SelectedItem = level; if (levels.SelectedIndex < 0) levels.SelectedIndex = 0;
            types.SelectedItem = type; if (types.SelectedIndex < 0) types.SelectedIndex = 0;
            if (!same) { ResetClashFilters(); search.Text = ""; foreach (var chip in quickFilters.Values) chip.IsChecked = false; TriageSaved(); }
            updating = false; Filter();
            Inspect();
        }
        public void SetFilters(string level, string type, string query)
        {
            updating = true; levels.SelectedItem = level ?? "All Levels"; types.SelectedItem = type ?? "All Types";
            search.Text = query ?? ""; updating = false; Filter();
        }
        public bool SelectIssue(long id)
        {
            var row = grid.Items.Cast<ClashRow>().FirstOrDefault(x => x.Id == id);
            grid.SelectedItem = row; return row != null;
        }
        private void Filter()
        {
            if (updating || snapshot == null) return;
            long? selected = Selected?.Id;
            var selectedIds = new HashSet<long>(grid.SelectedItems.Cast<ClashRow>().Select(x => x.Id));
            string level = levels.SelectedIndex <= 0 ? null : levels.SelectedItem as string;
            var rows = snapshot.Issues.Where(x => x.Matches(level, null, search.Text) && MatchesQuickFilters(x)).ToList();
            updating = true;
            rows = FilterClashCategories(rows);
            var view = new ListCollectionView(rows);
            var previousSort = (grid.ItemsSource as ListCollectionView)?.SortDescriptions.ToArray();
            grid.ItemsSource = view;
            ApplyListLayout(view, previousSort);
            count.Text = rows.Count + " shown / " + snapshot.Issues.Count + " saved clashes" + (rows.Count == 0 ? " · No matches" : "");
            grid.SelectedItem = rows.FirstOrDefault(x => x.Id == selected);
            foreach (var row in rows.Where(x => selectedIds.Contains(x.Id))) if (!grid.SelectedItems.Contains(row)) grid.SelectedItems.Add(row);
            updating = false;
            Inspect();
        }
        private void Inspect()
        {
            if (updating) return;
            var row = Selected;
            UpdateTriageSelection();
            UpdateReviewCard(row);
            if (previewIssue.HasValue && previewIssue != row?.Id) InspectionSession.End();
            previewPending = row != null && previewIssue != row.Id;
            selectionTimer.Stop(); if (previewPending) selectionTimer.Start();
            UpdateButtons();
        }
        private void UpdateButtons()
        {
            foreach (var button in buttons)
            {
                string label = (string)button.Content;
                bool navigation = label == "Select in Revit" || label == "Rotate 90°" || label == "Pin as view" || label == "⚙";
                button.IsEnabled = !busy && (!navigation || Selected != null);
                if (label.StartsWith("Copy", StringComparison.Ordinal)) button.IsEnabled = Selected != null;
                if(label=="Pin as view")button.IsEnabled=!busy&&Selected!=null&&previewIssue==Selected.Id;
            }
            foreach (var tab in viewTabs.Values) tab.IsEnabled = !busy && Selected != null;
            foreach (var chip in categories.Values) chip.IsEnabled = !busy;
            includeLinks.IsEnabled = !busy;
            UpdateTriageButtons();
            UpdateReviewNavigation();
        }
        public void SetBusy(bool value, string text)
        {
            busy = value; message.Text = text;
            if (!value && scanProgress.Visibility == Visibility.Visible) { scanStatus.Text = text; scanProgress.Visibility = Visibility.Collapsed; }
            UpdateButtons();
        }
        public void UpdateScanProgress(string stage, int current, int total)
        {
            scanStatus.Text = stage + (total > 0 ? " " + current + "/" + total : "");
            scanProgress.Visibility = Visibility.Visible; scanProgress.IsIndeterminate = total <= 0;
            scanProgress.Value = total > 0 ? Math.Min(100, 100.0 * current / total) : 0;
            // Process render work only; never pump input/Revit commands during a scan.
            Dispatcher.Invoke(DispatcherPriority.Render, new Action(() => { }));
        }
        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.F && Keyboard.Modifiers == ModifierKeys.Control)
            { search.Focus(); search.SelectAll(); e.Handled = true; return; }
            if (Keyboard.Modifiers != ModifierKeys.None || Keyboard.FocusedElement is TextBox || Keyboard.FocusedElement is ComboBox) return;
            bool inGrid = grid.IsKeyboardFocusWithin;
            if (!inGrid) return; // Preserve Space/arrow behavior in scan chips, tabs and sliders.
            if (e.Key == Key.Up || e.Key == Key.Down)
            {
                MoveReview(e.Key == Key.Down ? 1 : -1);
                e.Handled = true;
            }
            else if (!busy && Selected != null && (e.Key == Key.Enter || e.Key == Key.Space))
            { previewPending = false; selectionTimer.Stop(); DashboardController.Request(e.Key == Key.Enter ? "3d" : "select"); e.Handled = true; }
        }
        public void ShowInspection(InspectionScene scene,string mode,int corner,bool useB,bool showContext,bool focus,double padding)
        {
            previewIssue=scene.IssueId;preview.Display(scene,mode,corner,useB,showContext,focus,padding);
            foreach (var tab in viewTabs) tab.Value.IsChecked = tab.Key == mode;
            previewTitle.Text="TEMPORARY "+mode.ToUpperInvariant()+" · "+(mode=="section"?"Axis "+(useB?"B":"A"):mode=="3d"?"Corner "+(corner+1):"Top view")+" · Project unchanged";
            UpdateButtons();
        }
        public void ClearInspection() { previewIssue=null;preview.Clear();previewTitle.Text="Select a clash for a 3D preview";UpdateButtons(); }
    }

}
