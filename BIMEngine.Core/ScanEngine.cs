using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using BIMEngine.Core.Collection;
using BIMEngine.Core.Geometry;
using BIMEngine.Core.Models;
using BIMEngine.Core.Spatial;
using SpatialElement = BIMEngine.Core.Models.SpatialElement;

namespace BIMEngine.Core
{
    public class ScanResult
    {
        public int ElementsCollected, CandidatePairsEvaluated, UniqueGeometryFetches;
        public List<ClashIssue> Issues = new List<ClashIssue>();
        public List<SpatialElement> Elements = new List<SpatialElement>();
        public List<string> Diagnostics = new List<string>();
        public Dictionary<string, double> Timings = new Dictionary<string, double>();
        public TimeSpan Elapsed;
    }
    public delegate void ScanProgress(string stageName, int current, int total);
    public class ScanEngine
    {
        private readonly ScanConfig _config;
        public ScanEngine(ScanConfig config) { _config = config; }
        public ScanResult RunScan(Document doc, ScanProgress progress = null)
        {
            if (doc == null || doc.IsFamilyDocument) throw new ArgumentException("Open a project document.");
            if (doc.Application.VersionNumber != "2024") throw new NotSupportedException("This build requires Revit 2024.");
            if (_config.Categories == null || _config.Categories.Count == 0 || _config.OctreeMaxDepth < 1 ||
                _config.OctreeMaxDepth > 16 || _config.OctreeMaxObjectsPerNode < 1 ||
                _config.CandidateQueryPaddingFeet < 0 || double.IsNaN(_config.CandidateQueryPaddingFeet) ||
                double.IsInfinity(_config.CandidateQueryPaddingFeet)) throw new ArgumentException("Invalid scan configuration.");
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var result = new ScanResult();
            progress?.Invoke("Collecting elements", 0, 0);
            result.Elements = new ElementCollector().Collect(doc, _config, result.Diagnostics, progress);
            var elements = result.Elements;
            result.ElementsCollected = elements.Count;
            result.Timings["collection"] = sw.Elapsed.TotalSeconds;
            var start = sw.Elapsed.TotalSeconds;
            progress?.Invoke("Building spatial index", 0, 0);
            var index = Octree.Build(elements.Select(e => e.ToSpatialEntry()), _config.OctreeMaxObjectsPerNode, _config.OctreeMaxDepth,
                (current, total) => progress?.Invoke("Building spatial index", current, total));
            var lookup = elements.ToDictionary(e => e.ScanKey);
            result.Timings["index"] = sw.Elapsed.TotalSeconds - start;
            start = sw.Elapsed.TotalSeconds;
            var seen = new HashSet<(long, long)>();
            var pairs = new List<CandidatePair>();
            foreach (var source in elements)
            {
                progress?.Invoke("Finding candidate pairs", pairs.Count, 0);
                foreach (var entry in index.Query(source.Bounds.Expand(_config.CandidateQueryPaddingFeet)))
                {
                    if (entry.ElementId == source.ScanKey) continue;
                    var key = (Math.Min(source.ScanKey, entry.ElementId), Math.Max(source.ScanKey, entry.ElementId));
                    if (seen.Add(key)) pairs.Add(new CandidatePair(source, lookup[entry.ElementId]));
                }
            }
            result.CandidatePairsEvaluated = pairs.Count;
            result.Timings["candidates"] = sw.Elapsed.TotalSeconds - start;
            start = sw.Elapsed.TotalSeconds;
            var intersection = new IntersectionService();
            using (var cache = new SolidCache(doc))
            {
                int done = 0;
                foreach (var pair in pairs)
                {
                    progress?.Invoke("Checking geometry", done++, pairs.Count);
                    var a = cache.GetSolids(pair.Source);
                    var b = cache.GetSolids(pair.Target);
                    HardClashResult best = new HardClashResult();
                    foreach (var sa in a) foreach (var sb in b)
                    {
                        progress?.Invoke("Checking geometry", done, pairs.Count);
                        var check = intersection.CheckHardClash(sa, sb);
                        if (check.Indeterminate) result.Diagnostics.Add("Boolean failed for " + pair.Source.ScanKey + "/" + pair.Target.ScanKey + ": " + check.Error);
                        if (check.IsClash && check.OverlapDepthFeet > best.OverlapDepthFeet) best = check;
                    }
                    if (best.IsClash) result.Issues.Add(new ClashIssue { ElementA = pair.Source, ElementB = pair.Target,
                        OverlapDepthFeet = best.OverlapDepthFeet, LocationX = best.Location.X,
                        LocationY = best.Location.Y, LocationZ = best.Location.Z });
                }
                result.UniqueGeometryFetches = cache.ApiCallCount;
                result.Diagnostics.AddRange(cache.Diagnostics);
                int distinct = pairs.SelectMany(p => new [] {p.Source.ScanKey, p.Target.ScanKey}).Distinct().Count();
                if (distinct != cache.ApiCallCount) throw new InvalidOperationException("Geometry cache invariant failed.");
            }
            result.Timings["geometry"] = sw.Elapsed.TotalSeconds - start;
            progress?.Invoke("Completed", pairs.Count, pairs.Count);
            result.Elapsed = sw.Elapsed;
            return result;
        }
    }
}

