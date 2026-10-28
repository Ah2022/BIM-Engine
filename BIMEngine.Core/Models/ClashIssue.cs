using System;

namespace BIMEngine.Core.Models
{
    public enum IssueStatus
    {
        Open,
        Reviewed,
        Resolved,
        Ignored
    }

    /// <summary>
    /// One detected issue (Step 6/7 of the pipeline). Phase 1 only ever sets
    /// IssueType = "HardClash" - it's a string rather than an enum so future
    /// engines (Compliance, QA/QC, ...) can introduce their own issue types
    /// without a Core rebuild forcing a schema migration.
    ///
    /// Carries full SpatialElement references (not just raw ids) so
    /// BimEngineDatabase can upsert Models/Elements from the issue alone,
    /// without a second round-trip to Revit.
    /// </summary>
    public class ClashIssue
    {
        public long IssueId;
        public string EngineSource = "ClashDetector";
        public string IssueType = "HardClash";

        public SpatialElement ElementA;
        /// <summary>Null for single-element issue types (e.g. a future QA/QC or
        /// Compliance check that flags one element on its own, not a pair).</summary>
        public SpatialElement ElementB;

        /// <summary>Positive overlap depth (ft) for a hard clash. Volume-based
        /// heuristic (cube root of intersection solid volume), not a true
        /// penetration depth along an axis - fine for triage/sorting, not for
        /// a precision measurement in a report.</summary>
        public double OverlapDepthFeet;

        public double LocationX, LocationY, LocationZ;

        public IssueStatus Status = IssueStatus.Open;
        public DateTime DetectedUtc = DateTime.UtcNow;
        public DateTime? ResolvedUtc;
        public string Notes;
    }
}
