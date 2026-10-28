using System;
using System.Collections.Generic;
using System.Linq;
using BIMEngine.Core.Spatial;
using BIMEngine.Core.Models;

class Program
{
    static int Main()
    {
        var random = new Random(20260920);
        var entries = new List<SpatialEntry>();
        for (int i = 0; i < 500; i++)
        {
            double x = random.NextDouble()*100, y = random.NextDouble()*100, z = random.NextDouble()*10;
            entries.Add(new SpatialEntry(i, new AABB(x,y,z,x+random.NextDouble()*30,y+2,z+1)));
        }
        var tree = Octree.Build(entries, 4, 8);
        if (tree.CountEntries() != entries.Count) throw new Exception("Entry loss");
        for (int i = 0; i < 1000; i++)
        {
            double x = random.NextDouble()*130, y = random.NextDouble()*102, z = random.NextDouble()*11;
            var q = new AABB(x,y,z,x+5,y+5,z+3);
            var expected = entries.Where(e => e.Bounds.Intersects(q)).Select(e => e.ElementId).OrderBy(id=>id);
            var actual = tree.Query(q).Select(e => e.ElementId).OrderBy(id=>id);
            if (!expected.SequenceEqual(actual)) throw new Exception("Query differs from brute force");
        }
        if (Octree.Build(new SpatialEntry[0]).CountEntries()!=0) throw new Exception("Empty tree");
        var box = new AABB(0,0,0,1,1,1);
        if (!box.Intersects(new AABB(1,0,0,2,1,1))) throw new Exception("Touching bounds");
        var elements = new [] { new SpatialElement { ElementId=1, ScanKey=1, Category="Pipes", Bounds=box },
            new SpatialElement { ElementId=2, ScanKey=2, Category="Ducts", Bounds=box } };
        var pairs = new CandidatePairFinder().FindCandidates(elements,
            Octree.Build(elements.Select(e=>e.ToSpatialEntry())), elements.ToDictionary(e=>e.ScanKey), 0);
        if(pairs.Count!=2 || pairs.Any(p=>p.Source==p.Target)) throw new Exception("Candidate pairs");
        Console.WriteLine("PASS: 1000 randomized octree queries match brute force; counts, empty tree, touching bounds, candidate self exclusion.");
        var linked = new SpatialElement { ElementId=1, ScanKey=3, IsFromLinkedDocument=true, LinkedDocumentReferenceId="link-A", Bounds=box };
        var linkedAgain = new SpatialElement { ElementId=1, ScanKey=4, IsFromLinkedDocument=true, LinkedDocumentReferenceId="link-B", Bounds=box };
        var repeated = new [] {elements[0], linked, linkedAgain};
        var distinctLookup = repeated.ToDictionary(e=>e.ScanKey);
        var linkedPairs = new CandidatePairFinder().FindCandidates(repeated,
            Octree.Build(repeated.Select(e=>e.ToSpatialEntry())), distinctLookup, 0);
        if (linkedPairs.Count != 6) throw new Exception("Host/link identity collapsed");
        Console.WriteLine("PASS: host and two link instances sharing ElementId retain all three distinct pairs.");
        InspectionChecks.Run();
        return 0;
    }
}
