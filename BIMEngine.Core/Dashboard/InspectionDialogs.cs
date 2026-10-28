using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Interop;
using Autodesk.Revit.UI;
using TextBox = System.Windows.Controls.TextBox;

namespace BIMEngine.Core.Dashboard
{
    public static class InspectionDialogs
    {
        private static Window Window(UIApplication app,string title,double width,double height)
        {
            var window=new Window {Title=title,Width=width,Height=height,WindowStartupLocation=WindowStartupLocation.CenterOwner,
                Background=DashboardPage.Navy,Foreground=DashboardPage.Ink,FontFamily=new System.Windows.Media.FontFamily("Segoe UI")};
            new WindowInteropHelper(window).Owner=app.MainWindowHandle;return window;
        }
        public static bool Pin(UIApplication app,string initial,bool allowAnnotation,out string name,out bool annotate)
        {
            var window=Window(app,"Pin clash as a Revit view",490,260);
            var panel=new StackPanel {Margin=new Thickness(18)};
            panel.Children.Add(DashboardPage.Text("Creates a persistent view in this project.",14));
            var input=new TextBox {Text=initial,Margin=new Thickness(0,14,0,10),Padding=new Thickness(6)};panel.Children.Add(input);
            var annotation=new CheckBox {Content="Save a red overlap-extent annotation (snapshot)",IsEnabled=allowAnnotation,Foreground=DashboardPage.Ink};panel.Children.Add(annotation);
            panel.Children.Add(DashboardPage.Text(allowAnnotation?"The live red solid overlay is recomputed when this pinned view opens.":"The 3D red solid overlay is transient and recomputed when this view opens.",11));
            var save=new Button {Content="Pin as view",Padding=new Thickness(12,7,12,7),Margin=new Thickness(0,16,0,0)};
            save.Click+=(s,e)=>{ if(!string.IsNullOrWhiteSpace(input.Text))window.DialogResult=true; };
            panel.Children.Add(save);window.Content=panel;
            bool accepted=window.ShowDialog()==true;name=input.Text.Trim();annotate=annotation.IsChecked==true;return accepted;
        }
        public static long[] Cleanup(UIApplication app)
        {
            var rows=PinnedClashViews.List(app.ActiveUIDocument.Document);
            foreach(var row in rows)if(row.Id==app.ActiveUIDocument.ActiveView.Id.Value)row.Protection="Active view";
            var window=Window(app,"Clean up BIM Engine views",850,470);
            var dock=new DockPanel {Margin=new Thickness(15)};
            var info=DashboardPage.Text("Select old BIM Engine views to delete. Sheet-placed, active and dependent-parent views are protected. Their own annotations are deleted with the selected views.",13);
            DockPanel.SetDock(info,Dock.Top);dock.Children.Add(info);
            var grid=new DataGrid {ItemsSource=rows,AutoGenerateColumns=false,CanUserAddRows=false,Margin=new Thickness(0,12,0,12)};
            grid.Columns.Add(new DataGridCheckBoxColumn {Header="Delete",Binding=new Binding("Selected"),Width=55});
            foreach(var column in new[]{"Name","Kind","Created","Protection"})grid.Columns.Add(new DataGridTextColumn {Header=column,Binding=new Binding(column),IsReadOnly=true,Width=column=="Name"?250:145});
            var controls=new StackPanel();
            var error=DashboardPage.Text("",12);controls.Children.Add(error);
            var remove=new Button {Content="Delete selected views",Padding=new Thickness(12,7,12,7)};
            remove.Click+=(s,e)=>{
                grid.CommitEdit(DataGridEditingUnit.Cell,true);grid.CommitEdit(DataGridEditingUnit.Row,true);
                var chosen=rows.Where(r=>r.Selected).ToList();
                if(chosen.Count==0) {error.Text="Select at least one view.";return;}
                if(chosen.Any(r=>r.Protection!="")) {error.Text="Uncheck protected views before deleting.";return;}
                window.DialogResult=true;
            };
            controls.Children.Add(remove);DockPanel.SetDock(controls,Dock.Bottom);dock.Children.Add(controls);dock.Children.Add(grid);window.Content=dock;
            return window.ShowDialog()==true?rows.Where(r=>r.Selected).Select(r=>r.Id).ToArray():Array.Empty<long>();
        }
    }
}
