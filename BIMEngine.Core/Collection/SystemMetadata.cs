using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;

namespace BIMEngine.Core.Collection
{
    /// <summary>Read semantic system types, not pipe family types or generic classifications.</summary>
    public sealed class SystemMetadata
    {
        public string SystemType = "";
        public string SystemClassification = "";
        public string SystemName = "";
        public string FamilyType = "";

        public static SystemMetadata Read(Element element)
        {
            var result = new SystemMetadata();
            var type = element.Document.GetElement(element.GetTypeId()) as ElementType;
            if (type != null) result.FamilyType = type.FamilyName + " : " + type.Name;
            var types = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
            var classes = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
            var names = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
            Action<MEPSystemType> addType = t => {
                if (t == null) return;
                types.Add(t.Name);
                classes.Add(t.SystemClassification.ToString());
            };
            Action<MEPSystem> addSystem = system => {
                if (system == null) return;
                names.Add(system.Name);
                addType(element.Document.GetElement(system.GetTypeId()) as MEPSystemType);
            };
            foreach (var parameter in new[] { BuiltInParameter.RBS_PIPING_SYSTEM_TYPE_PARAM, BuiltInParameter.RBS_DUCT_SYSTEM_TYPE_PARAM })
            {
                var value = element.get_Parameter(parameter);
                if (value?.StorageType == StorageType.ElementId) addType(element.Document.GetElement(value.AsElementId()) as MEPSystemType);
            }
            ConnectorManager manager = null;
            if (element is MEPCurve curve) { addSystem(curve.MEPSystem); manager = curve.ConnectorManager; }
            else if (element is FamilyInstance family) manager = family.MEPModel?.ConnectorManager;
            if (manager != null)
                foreach (Connector connector in manager.Connectors)
                {
                    if (connector.Domain != Domain.DomainPiping && connector.Domain != Domain.DomainHvac) continue;
                    try { addSystem(connector.MEPSystem); }
                    catch (Autodesk.Revit.Exceptions.InvalidOperationException) { /* Logical/unassigned connector. */ }
                }
            result.SystemType = string.Join(" / ", types);
            result.SystemClassification = string.Join(" / ", classes);
            result.SystemName = string.Join(" / ", names);
            if (types.Count > 1) result.SystemType = "Multiple systems: " + result.SystemType;
            return result;
        }
    }
}
