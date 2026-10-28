using System;
using System.Collections.Generic;
using System.Linq;
using BIMEngine.Core.Dashboard;

static class InspectionChecks
{
    public static void Run()
    {
        var random=new Random(21);
        for(int i=0;i<500;i++)
        {
            var scene=new InspectionScene { AxisA=new Point3(random.NextDouble()-.5,random.NextDouble()-.5,random.NextDouble()-.5),AxisB=new Point3(0,0,1),
                Min=new Point3(-10,-20,-3),Max=new Point3(15,30,9),Clash=new Point3(2,3,4) };
            foreach(var mode in new[]{"2d","3d","section"})for(int corner=0;corner<4;corner++)foreach(bool b in new[]{false,true})
            {
                scene.Axes(mode,corner,b,out var r,out var u,out var f);
                if(Math.Abs(r.Length-1)>1e-8||Math.Abs(u.Length-1)>1e-8||Math.Abs(f.Length-1)>1e-8||Math.Abs(r.Dot(u))+Math.Abs(r.Dot(f))+Math.Abs(u.Dot(f))>1e-8)
                    throw new Exception("Camera/section basis is not orthonormal");
            }
            scene.Frame(2,false,out var min,out var max);
            if(min.X!=-12||max.Y!=32)throw new Exception("Element frame padding");
            scene.Frame(2,true,out min,out max);
            if(min.X!=0||max.Y!=5)throw new Exception("Clash focus frame");
            var triangle=new List<Point3>{new Point3(-2,0,0),new Point3(2,0,0),new Point3(0,3,0)};
            var clipped=InspectionScene.Clip(triangle,new Point3(),new Point3(1,0,0),0);
            if(clipped.Any(p=>p.X>1e-9)||clipped.Count<3)throw new Exception("Section clipping failed");
        }
        Console.WriteLine("PASS: 500 camera/section-axis trials (including vertical), fitted/focused bounds, and half-space clipping.");
    }
}
