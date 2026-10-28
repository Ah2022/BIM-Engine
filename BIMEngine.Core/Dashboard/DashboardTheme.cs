using System;
using System.ComponentModel;
using System.Windows.Data;
using System.Windows.Media;
using Autodesk.Revit.UI;

namespace BIMEngine.Core.Dashboard
{
    // Bound brush colours remain live even inside sealed WPF styles/templates.
    public sealed class DashboardPalette : INotifyPropertyChanged
    {
        public bool Dark { get; private set; }
        public Color Background => ColorOf(Dark ? "#252629" : "#F3F3F3");
        public Color Surface => ColorOf(Dark ? "#303236" : "#FFFFFF");
        public Color Alternate => ColorOf(Dark ? "#383A3F" : "#EAEDEF");
        public Color Text => ColorOf(Dark ? "#F1F2F3" : "#202326");
        public Color Secondary => ColorOf(Dark ? "#B9BEC6" : "#555E69");
        public Color Accent => ColorOf(Dark ? "#51C8BD" : "#007A72");
        public Color Reviewed => ColorOf(Dark ? "#75BFFF" : "#1766A5");
        public Color Selection => ColorOf(Dark ? "#155550" : "#C8EAE6");
        public Color System0 => ColorOf(Dark ? "#48C9B0" : "#007C68");
        public Color System1 => ColorOf(Dark ? "#75BFFF" : "#1766A5");
        public Color System2 => ColorOf(Dark ? "#E4AE68" : "#925500");
        public Color System3 => ColorOf(Dark ? "#CC9FF4" : "#7540A3");
        public Color System4 => ColorOf(Dark ? "#F491B1" : "#A52D62");
        public Color System5 => ColorOf(Dark ? "#B8CF72" : "#5D711B");
        private static Color ColorOf(string value) => (Color)ColorConverter.ConvertFromString(value);
        public event PropertyChangedEventHandler PropertyChanged;
        public void SetDark(bool dark)
        {
            if (Dark == dark) return;
            Dark = dark; PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(null));
        }
    }

    public static class DashboardTheme
    {
        public static readonly DashboardPalette Palette = new DashboardPalette();
        public static readonly Brush Background = Brush("Background"), Surface = Brush("Surface"), Alternate = Brush("Alternate"),
            Text = Brush("Text"), Secondary = Brush("Secondary"), Accent = Brush("Accent"), Reviewed = Brush("Reviewed"), Selection = Brush("Selection");
        public static readonly Brush[] Systems = { Brush("System0"), Brush("System1"), Brush("System2"), Brush("System3"), Brush("System4"), Brush("System5") };
        private static Brush Brush(string name)
        {
            var brush = new SolidColorBrush();
            BindingOperations.SetBinding(brush, SolidColorBrush.ColorProperty, new Binding(name) { Source = Palette });
            return brush;
        }
        public static void FollowRevit() => Palette.SetDark(UIThemeManager.CurrentTheme == UITheme.Dark);
    }
}
