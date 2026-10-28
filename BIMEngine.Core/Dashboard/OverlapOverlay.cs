using System;
using System.Linq;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.DirectContext3D;
using Autodesk.Revit.DB.ExternalService;

namespace BIMEngine.Core.Dashboard
{
    /// <summary>In-memory triangles in pinned Revit views; never creates a DirectShape.</summary>
    public sealed class OverlapOverlay : IDirectContext3DServer
    {
        private static readonly Guid Id=new Guid("137D8AA2-CAB6-4666-901D-532A0628F884");
        private static OverlapOverlay server;
        private sealed class Frame
        {
            public Document Document; public long ViewId; public InspectionScene Scene;
        }
        private volatile Frame frame;
        public static string LastError { get; private set; }
        public static int RenderCount { get; private set; }
        public static void Show(Document doc,View view,InspectionScene scene)
        {
            if(server==null)
            {
                var service=ExternalServiceRegistry.GetService(ExternalServices.BuiltInExternalServices.DirectContext3DService) as MultiServerService;
                if(service==null)throw new InvalidOperationException("Transient Revit graphics service is unavailable.");
                server=new OverlapOverlay();service.AddServer(server);
                var active=service.GetActiveServerIds();if(!active.Contains(Id))active.Add(Id);service.SetActiveServers(active);
            }
            LastError=null;server.frame=new Frame { Document=doc,ViewId=view.Id.Value,Scene=scene };
        }
        public static void Clear() { if(server!=null)server.frame=null; }
        public Guid GetServerId()=>Id;
        public ExternalServiceId GetServiceId()=>ExternalServices.BuiltInExternalServices.DirectContext3DService;
        public string GetName()=>"BIM Engine overlap preview";
        public string GetVendorId()=>"BIME";
        public string GetDescription()=>"Transient selected-clash geometry; no model elements";
        public string GetApplicationId()=>"BIMEngine";
        public string GetSourceId()=>"BIMEngine";
        public bool UsesHandles()=>false;
        public bool CanExecute(View view)
        {
            var value=frame;
            return value!=null&&view.Document.Equals(value.Document)&&view.Id.Value==value.ViewId;
        }
        public bool UseInTransparentPass(View view)=>true;
        public Outline GetBoundingBox(View view)
        {
            var value=frame;
            return value==null?new Outline(XYZ.Zero,XYZ.BasisX):new Outline(InspectionGeometry.XYZ(value.Scene.Min),InspectionGeometry.XYZ(value.Scene.Max));
        }
        public void RenderScene(View view,DisplayStyle style)
        {
            var value=frame;
            if(value==null||!CanExecute(view))return;
            try
            {
                // Render in small batches to stay within 16-bit index limits.
                foreach(var mesh in value.Scene.Meshes.Where(m=>m.Role<3))
                {
                    bool transparent=mesh.Role!=2;
                    if(DrawContext.IsTransparentPass()!=transparent)continue;
                    var c=InspectionViewport.ColorFor(mesh.Role);
                    var color=new ColorWithTransparency(c.R,c.G,c.B,transparent?110u:0u);
                    for(int start=0;start<mesh.Points.Length;start+=30000)
                    {
                        if(DrawContext.IsInterrupted())return;
                        int count=Math.Min(30000,mesh.Points.Length-start);
                        int vs=count*VertexPositionColored.GetSizeInFloats(),isize=(count/3)*IndexTriangle.GetSizeInShortInts();
                        using(var vb=new VertexBuffer(vs))using(var ib=new IndexBuffer(isize))
                        using(var format=new VertexFormat(VertexFormatBits.PositionColored))
                        using(var effect=new EffectInstance(VertexFormatBits.PositionColored))
                        {
                            vb.Map(vs);var vertices=vb.GetVertexStreamPositionColored();
                            for(int i=0;i<count;i++)vertices.AddVertex(new VertexPositionColored(InspectionGeometry.XYZ(mesh.Points[start+i]),color));
                            vb.Unmap();ib.Map(isize);var indices=ib.GetIndexStreamTriangle();
                            for(int i=0;i<count;i+=3)indices.AddTriangle(new IndexTriangle(i,i+1,i+2));
                            ib.Unmap();DrawContext.FlushBuffer(vb,count,ib,isize,format,effect,PrimitiveType.TriangleList,0,count/3);
                        }
                    }
                }
                RenderCount++;
            }
            catch(Exception ex) { LastError=ex.Message; }
        }
    }
}
