using Autodesk.Revit.DB;

namespace BIMEngine.Core.Geometry
{
    public struct HardClashResult
    {
        public bool IsClash;
        public bool Indeterminate;
        public string Error;
        public double OverlapDepthFeet;
        public XYZ Location;
    }

    public class IntersectionService
    {
        public HardClashResult CheckHardClash(Solid solidA, Solid solidB)
        {
            try
            {
                using (var overlap = BooleanOperationsUtils.ExecuteBooleanOperation(solidA, solidB, BooleanOperationsType.Intersect))
                {
                    if (overlap == null || overlap.Volume <= 1e-9) return new HardClashResult();
                    return new HardClashResult { IsClash = true,
                        OverlapDepthFeet = System.Math.Pow(overlap.Volume, 1.0/3.0),
                        Location = overlap.ComputeCentroid() };
                }
            }
            catch (Autodesk.Revit.Exceptions.InvalidOperationException ex)
            { return new HardClashResult { Indeterminate = true, Error = ex.Message }; }
            catch (Autodesk.Revit.Exceptions.ArgumentException ex)
            { return new HardClashResult { Indeterminate = true, Error = ex.Message }; }
        }
    }
}

