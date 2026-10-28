using System.Windows;
using System.Windows.Markup;

namespace BIMEngine.Core.Dashboard
{
    internal static class DashboardThemeControls
    {
        private static readonly ResourceDictionary Styles = Create();
        internal static Style ButtonStyle => (Style)Styles["Action"];
        internal static Style ComboStyle => (Style)Styles["Choice"];
        private static ResourceDictionary Create()
        {
            var styles = (ResourceDictionary)XamlReader.Parse(@"
<ResourceDictionary xmlns='http://schemas.microsoft.com/winfx/2006/xaml/presentation' xmlns:x='http://schemas.microsoft.com/winfx/2006/xaml'>
  <Style x:Key='Action' TargetType='Button'>
    <Setter Property='Template'><Setter.Value><ControlTemplate TargetType='Button'>
      <Border x:Name='Frame' Background='{TemplateBinding Background}' BorderBrush='{TemplateBinding BorderBrush}' BorderThickness='1' CornerRadius='4' Padding='{TemplateBinding Padding}'>
        <ContentPresenter HorizontalAlignment='Center' VerticalAlignment='Center' RecognizesAccessKey='True'/>
      </Border>
      <ControlTemplate.Triggers>
        <Trigger Property='IsMouseOver' Value='True'><Setter TargetName='Frame' Property='Background' Value='{DynamicResource Alternate}'/></Trigger>
        <Trigger Property='IsKeyboardFocused' Value='True'><Setter TargetName='Frame' Property='BorderThickness' Value='2'/></Trigger>
        <Trigger Property='IsEnabled' Value='False'><Setter Property='Opacity' Value='.45'/></Trigger>
      </ControlTemplate.Triggers>
    </ControlTemplate></Setter.Value></Setter>
  </Style>
  <Style x:Key='ChoiceItem' TargetType='ComboBoxItem'>
    <Setter Property='Foreground' Value='{DynamicResource Ink}'/><Setter Property='Background' Value='{DynamicResource Surface}'/>
    <Setter Property='Padding' Value='7,5'/>
    <Setter Property='Template'><Setter.Value><ControlTemplate TargetType='ComboBoxItem'>
      <Border Background='{TemplateBinding Background}' Padding='{TemplateBinding Padding}'><ContentPresenter/></Border>
    </ControlTemplate></Setter.Value></Setter>
    <Style.Triggers><Trigger Property='IsHighlighted' Value='True'><Setter Property='Background' Value='{DynamicResource Selection}'/></Trigger></Style.Triggers>
  </Style>
  <Style x:Key='Choice' TargetType='ComboBox'>
    <Setter Property='Foreground' Value='{DynamicResource Ink}'/><Setter Property='Background' Value='{DynamicResource Surface}'/>
    <Setter Property='BorderBrush' Value='{DynamicResource Muted}'/><Setter Property='ItemContainerStyle' Value='{StaticResource ChoiceItem}'/>
    <Setter Property='Template'><Setter.Value><ControlTemplate TargetType='ComboBox'>
      <Grid>
        <ToggleButton Focusable='False' IsChecked='{Binding IsDropDownOpen, RelativeSource={RelativeSource TemplatedParent}, Mode=TwoWay}' Background='{TemplateBinding Background}' BorderBrush='{TemplateBinding BorderBrush}'>
          <ToggleButton.Template><ControlTemplate TargetType='ToggleButton'>
            <Border Background='{TemplateBinding Background}' BorderBrush='{TemplateBinding BorderBrush}' BorderThickness='1' CornerRadius='3'>
              <TextBlock Text='▾' Foreground='{DynamicResource Ink}' HorizontalAlignment='Right' VerticalAlignment='Center' Margin='0,0,7,0'/>
            </Border>
          </ControlTemplate></ToggleButton.Template>
        </ToggleButton>
        <ContentPresenter IsHitTestVisible='False' Content='{TemplateBinding SelectionBoxItem}' ContentTemplate='{TemplateBinding SelectionBoxItemTemplate}' Margin='6,0,24,0' VerticalAlignment='Center' ClipToBounds='True'/>
        <Popup x:Name='PART_Popup' IsOpen='{TemplateBinding IsDropDownOpen}' Placement='Bottom' AllowsTransparency='True' Focusable='False'>
          <Border Background='{DynamicResource Surface}' BorderBrush='{DynamicResource Muted}' BorderThickness='1' MinWidth='{Binding ActualWidth, RelativeSource={RelativeSource TemplatedParent}}' MaxHeight='280'>
            <ScrollViewer CanContentScroll='True'><ItemsPresenter KeyboardNavigation.DirectionalNavigation='Contained'/></ScrollViewer>
          </Border>
        </Popup>
      </Grid>
      <ControlTemplate.Triggers><Trigger Property='IsEnabled' Value='False'><Setter Property='Opacity' Value='.45'/></Trigger></ControlTemplate.Triggers>
    </ControlTemplate></Setter.Value></Setter>
  </Style>
</ResourceDictionary>");
            foreach (Style style in styles.Values)
            {
                style.Resources["Surface"] = DashboardTheme.Surface; style.Resources["Ink"] = DashboardTheme.Text;
                style.Resources["Muted"] = DashboardTheme.Secondary; style.Resources["Alternate"] = DashboardTheme.Alternate;
                style.Resources["Selection"] = DashboardTheme.Selection;
            }
            return styles;
        }
    }
}
