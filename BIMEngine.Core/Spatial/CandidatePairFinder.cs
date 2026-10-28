using System.Collections.Generic;
using System.Linq;
using BIMEngine.Core.Models;

namespace BIMEngine.Core.Spatial
{
    public struct CandidatePair
    {
        public SpatialElement Source;
        public SpatialElement Target;

        public CandidatePair(SpatialElement source, SpatialElement target)
        {
            Source = source;
            Target = target;
        }
    }

    /// <summary>
    /// Step 4. For each "source" element (e.g. every pipe), query the octree
    /// built from "target" elements (e.g. ducts, cable trays, structure) for
    /// only the entries whose bounds fall near it, instead of the 5000x5000
    /// all-pairs comparison.
    /// </summary>
    public class CandidatePairFinder
    {
        /// <param name="sourceElements">The elements you're checking, e.g. all pipes.</param>
        /// <param name="targetIndex">Octree already built from the target population (e.g. all ducts).</param>
        /// <param name="targetLookup">ScanKey -> SpatialElement; never key by a document-local Revit ElementId.</param>
        /// <param name="queryPaddingFeet">Expand each element's box by this much before querying.
        /// Phase 1 is hard-clash only, so this should just be a small epsilon (ScanConfig.CandidateQueryPaddingFeet)
        /// to guard floating-point edge cases at box boundaries - not a clearance distance.</param>
        public List<CandidatePair> FindCandidates(
            IEnumerable<SpatialElement> sourceElements,
            Octree targetIndex,
            Dictionary<long, SpatialElement> targetLookup,
            double queryPaddingFeet)
        {
            var pairs = new List<CandidatePair>();

            foreach (var source in sourceElements)
            {
                AABB queryRegion = source.Bounds.Expand(queryPaddingFeet);
                List<SpatialEntry> nearby = targetIndex.Query(queryRegion);

                foreach (var entry in nearby)
                {
                    if (!targetLookup.TryGetValue(entry.ElementId, out var target))
                        continue;

                    // Skip self-pairs when source and target populations overlap
                    // (e.g. running a Pipes-vs-Pipes crossing check in a later phase).
                    if (target.ScanKey == source.ScanKey)
                        continue;

                    pairs.Add(new CandidatePair(source, target));
                }
            }

            return pairs;
        }
    }
}
