using System.Collections.Generic;

namespace BIMEngine.Core.Models
{
    /// <summary>
    /// Everything one Model Scanner run needs. Serialized to/from the pyRevit
    /// per-user JSON config, and passed into ScanEngine.RunScan().
    ///
    /// Phase 1 scope is hard clashes only - no clearance checking, so there's
    /// no clearance-rule list here. If clearance checking comes back as its
    /// own module later (per the multi-engine platform plan), it gets its own
    /// config class rather than reusing this one, since it needs a real
    /// solid-to-solid distance calculation this phase doesn't implement
    /// (the previous revision's clearance path was removed rather than left
    /// half-built on a distance stub).
    /// </summary>
    public class ScanConfig
    {
        /// <summary>Revit built-in category names to collect. Defaults to the Phase 1 set.</summary>
        public List<string> Categories = new List<string>
        {
            "Pipes", "Ducts", "Cable Trays", "Structural Framing", "Structural Columns"
        };

        /// <summary>Whether to also scan structural/host categories inside linked models.</summary>
        public bool IncludeLinkedDocuments = true;

        // Octree tuning - defaults are fine for typical MEP density; expose in
        // the Settings pushbutton for cases that need adjustment.
        public int OctreeMaxObjectsPerNode = 16;
        public int OctreeMaxDepth = 8;

        /// <summary>Small padding (feet) added to each element's box before querying
        /// the octree for neighbors. Zero is technically sufficient for hard-clash-only
        /// detection since Octree.Query uses inclusive bounds comparisons, but a small
        /// epsilon guards against floating-point edge cases at box boundaries.</summary>
        public double CandidateQueryPaddingFeet = 0.01;
    }
}
