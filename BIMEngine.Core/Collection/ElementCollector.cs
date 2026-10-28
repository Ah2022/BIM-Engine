using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using BIMEngine.Core.Models;
using BIMEngine.Core.Spatial;
using SpatialElement = BIMEngine.Core.Models.SpatialElement;

namespace BIMEngine.Core.Collection
{
    /// <summary>
    /// Step 1 (Collect elements) + Step 2 (Get bounding boxes, location, level).
    ///
    /// This is the ONLY place in the whole pipeline that reads ElementId,
    /// Category, BoundingBox, Location, and Level from the live Revit API for
    /// the full element population - exactly once per element, into
    /// SpatialElement. Everything downstream (Octree, CandidatePairFinder)
    /// works from that in-memory snapshot only. See the README for the
    /// import-graph evidence backing this claim.
    ///
    /// Collects from the host document AND every loaded linked document,
    /// transforming linked bounding boxes/locations into host coordinates up
    /// front. This is deliberate from day one rather than a later fix: a
    /// FilteredElementCollector(doc) call only ever sees the host document,
    /// so structural elements (or any target category) living in a linked
    /// model are otherwise invisible to the scan.
    /// </summary>
    public class ElementCollector
    {
        private static readonly Dictionary<string, BuiltInCategory> CategoryMap = new Dictionary<string, BuiltInCategory>
        {
            { "Pipes", BuiltInCategory.OST_PipeCurves },
            { "Ducts", BuiltInCategory.OST_DuctCurves },
            { "Cable Trays", BuiltInCategory.OST_CableTray },
            { "Structural Framing", BuiltInCategory.OST_StructuralFraming },
            { "Structural Columns", BuiltInCategory.OST_StructuralColumns },
            { "Duct Terminals", BuiltInCategory.OST_DuctTerminal },
            { "Air Terminals", BuiltInCategory.OST_DuctTerminal },
            { "Pipe Accessories", BuiltInCategory.OST_PipeAccessory },
        };

        // Category-dependent - Revit has no single universal "level" property on
        // Element, so this tries several common BuiltInParameters in order.
        // Verify against your actual categories once compiled/tested; this is a
        // reasonable default chain, not a guaranteed-correct one for every family.
        private static readonly BuiltInParameter[] LevelParameterCandidates =
        {
            BuiltInParameter.RBS_START_LEVEL_PARAM,          // MEP curves: pipes, ducts, cable trays
            BuiltInParameter.SCHEDULE_LEVEL_PARAM,            // many system families
            BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM,  // structural framing
            BuiltInParameter.FAMILY_BASE_LEVEL_PARAM,         // columns (base level)
            BuiltInParameter.FAMILY_LEVEL_PARAM,              // some hosted families
        };

        public List<SpatialElement> Collect(Document hostDoc, ScanConfig config,
            List<string> diagnostics = null, ScanProgress progress = null)
        {
            var results = new List<SpatialElement>();

            var categoryIds = config.Categories
                .Where(CategoryMap.ContainsKey)
                .Select(c => CategoryMap[c])
                .Distinct()
                .ToList();

            if (categoryIds.Count == 0)
                return results;

            var filter = new ElementMulticategoryFilter(categoryIds);

            // Host document
            var hostCollector = new FilteredElementCollector(hostDoc)
                .WherePasses(filter)
                .WhereElementIsNotElementType();

            foreach (var el in hostCollector)
            {
                progress?.Invoke("Collecting host elements", results.Count, 0);
                var info = ToSpatialElement(el, config, isLinked: false, linkedDocTitle: null, linkTransform: null, linkRefId: null);
                if (info != null)
                    results.Add(info);
                else diagnostics?.Add("No bounding box: host element " + el.Id.Value);
            }

            // Linked documents
            if (config.IncludeLinkedDocuments)
            {
                var linkInstances = new FilteredElementCollector(hostDoc)
                    .OfClass(typeof(RevitLinkInstance))
                    .Cast<RevitLinkInstance>();

                foreach (var linkInstance in linkInstances)
                {
                    var linkedDoc = linkInstance.GetLinkDocument();
                    if (linkedDoc == null) { diagnostics?.Add("Unloaded link: " + linkInstance.UniqueId); continue; }
                    if (new FilteredElementCollector(linkedDoc).OfClass(typeof(RevitLinkInstance)).Any())
                        diagnostics?.Add("Nested Revit links are outside the scan scope: " + linkInstance.UniqueId);

                    Transform linkTransform = linkInstance.GetTotalTransform();

                    var linkedCollector = new FilteredElementCollector(linkedDoc)
                        .WherePasses(filter)
                        .WhereElementIsNotElementType();

                    foreach (var el in linkedCollector)
                    {
                        progress?.Invoke("Collecting linked elements", results.Count, 0);
                        var info = ToSpatialElement(el, config, isLinked: true,
                            linkedDocTitle: linkedDoc.Title,
                            linkTransform: linkTransform,
                            linkRefId: linkInstance.UniqueId);
                        if (info != null)
                            results.Add(info);
                        else diagnostics?.Add("No bounding box: " + linkInstance.UniqueId + "/" + el.Id.Value);
                    }
                }
            }

            for (int i = 0; i < results.Count; i++) results[i].ScanKey = i + 1;
            return results;
        }

        private SpatialElement ToSpatialElement(Element el, ScanConfig config, bool isLinked, string linkedDocTitle, Transform linkTransform, string linkRefId)
        {
            BoundingBoxXYZ bbox = el.get_BoundingBox(null);
            if (bbox == null)
                return null; // elements with no geometry in this view/context

            AABB bounds = isLinked
                ? TransformedBounds(bbox, linkTransform)
                : new AABB(bbox.Min.X, bbox.Min.Y, bbox.Min.Z, bbox.Max.X, bbox.Max.Y, bbox.Max.Z);

            XYZ location = GetRepresentativeLocation(el, bbox);
            if (isLinked)
                location = linkTransform.OfPoint(location);

            ResolveLevel(el, out string levelName, out long levelId);
            var system = SystemMetadata.Read(el);

            return new SpatialElement
            {
                ElementId = el.Id.Value,
                ElementUniqueId = el.UniqueId,
                DocumentKey = DocumentIdentity.Get(el.Document),
                Category = ResolveCategoryLabel(el, config),
                SystemType = system.SystemType,
                SystemClassification = system.SystemClassification,
                SystemName = system.SystemName,
                FamilyType = system.FamilyType,
                DocumentTitle = isLinked ? linkedDocTitle : el.Document.Title,
                IsFromLinkedDocument = isLinked,
                LinkedDocumentReferenceId = linkRefId,
                Bounds = bounds,
                LocationX = location.X,
                LocationY = location.Y,
                LocationZ = location.Z,
                LevelName = levelName,
                LevelId = levelId
            };
        }

        /// <summary>Point-based elements (columns) use LocationPoint; line-based
        /// elements (pipes, ducts, cable trays, framing) use LocationCurve - take
        /// its midpoint. Falls back to the bounding box center for anything with
        /// neither (rare, but cheaper than a null check leaking downstream).</summary>
        private XYZ GetRepresentativeLocation(Element el, BoundingBoxXYZ bbox)
        {
            var loc = el.Location;
            if (loc is LocationPoint lp)
                return lp.Point;
            if (loc is LocationCurve lc)
                return lc.Curve.Evaluate(0.5, true);
            return (bbox.Min + bbox.Max) * 0.5;
        }

        private void ResolveLevel(Element el, out string levelName, out long levelId)
        {
            foreach (var bip in LevelParameterCandidates)
            {
                Parameter param = el.get_Parameter(bip);
                if (param == null || param.StorageType != StorageType.ElementId)
                    continue;

                ElementId paramLevelId = param.AsElementId();
                if (paramLevelId == null || paramLevelId == ElementId.InvalidElementId)
                    continue;

                if (el.Document.GetElement(paramLevelId) is Level level)
                {
                    levelName = level.Name;
                    levelId = level.Id.Value;
                    return;
                }
            }
            levelName = "Unknown";
            levelId = -1;
        }

        /// <summary>Transforms a linked-document bounding box's 8 corners into host
        /// coordinates and re-derives the AABB, since a rotated link can otherwise
        /// produce an under-sized box if you only transform Min/Max directly.</summary>
        private AABB TransformedBounds(BoundingBoxXYZ bbox, Transform transform)
        {
            var corners = new[]
            {
                new XYZ(bbox.Min.X, bbox.Min.Y, bbox.Min.Z),
                new XYZ(bbox.Max.X, bbox.Min.Y, bbox.Min.Z),
                new XYZ(bbox.Min.X, bbox.Max.Y, bbox.Min.Z),
                new XYZ(bbox.Max.X, bbox.Max.Y, bbox.Min.Z),
                new XYZ(bbox.Min.X, bbox.Min.Y, bbox.Max.Z),
                new XYZ(bbox.Max.X, bbox.Min.Y, bbox.Max.Z),
                new XYZ(bbox.Min.X, bbox.Max.Y, bbox.Max.Z),
                new XYZ(bbox.Max.X, bbox.Max.Y, bbox.Max.Z),
            };

            double minX = double.MaxValue, minY = double.MaxValue, minZ = double.MaxValue;
            double maxX = double.MinValue, maxY = double.MinValue, maxZ = double.MinValue;

            foreach (var c in corners)
            {
                XYZ t = transform.OfPoint(c);
                minX = System.Math.Min(minX, t.X); maxX = System.Math.Max(maxX, t.X);
                minY = System.Math.Min(minY, t.Y); maxY = System.Math.Max(maxY, t.Y);
                minZ = System.Math.Min(minZ, t.Z); maxZ = System.Math.Max(maxZ, t.Z);
            }

            return new AABB(minX, minY, minZ, maxX, maxY, maxZ);
        }

        /// <summary>Maps a category that has multiple BuiltInCategory aliases (e.g. Air
        /// Terminals / Duct Terminals both live under OST_DuctTerminal) back to the
        /// config label the user configured, falling back to the element's own
        /// category name for anything not explicitly mapped.</summary>
        private string ResolveCategoryLabel(Element el, ScanConfig config)
        {
            string catName = el.Category?.Name ?? "Unknown";
            foreach (var label in config.Categories)
                if (CategoryMap.TryGetValue(label, out var bic) && (long)bic == el.Category?.Id.Value)
                    return label;
            return catName;
        }
    }
}
